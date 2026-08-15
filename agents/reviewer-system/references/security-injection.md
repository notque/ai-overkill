# Injection and Code Execution Patterns

Load when reviewing code that touches subprocess calls, eval/exec, template rendering, deserialization, or deep-merge of user-controlled objects.

Untrusted input reaches a sink that executes code. Keep user data out of code-execution paths — use safe APIs, parameterized interfaces, and strict input validation.

---

## Pass Arguments as Arrays to Subprocess Calls

Use array form with `shell=False`. Prevents shell metacharacter interpretation.

### Correct Pattern

**Python:**
```python
import subprocess
subprocess.run(["git", "clone", "--", user_repo_url], check=True)
subprocess.run(["convert", user_filename, "out.png"], shell=False, check=True)
```

**TypeScript/Node:**
```ts
import { execFile } from 'node:child_process';
execFile('git', ['clone', '--', userRepoUrl], (err, stdout) => {
  if (err) throw err;
});
```

**Go:**
```go
cmd := exec.Command("git", "clone", "--", userRepoURL)
if err := cmd.Run(); err != nil {
    return fmt.Errorf("clone failed: %w", err)
}
```

### Why This Matters

Shell injection: `subprocess.run(f"git clone {url}", shell=True)` lets attacker supply `; rm -rf /`.

**CVEs:** CVE-2021-22205 (GitLab ExifTool RCE), CVE-2024-27980 (Node.js BatBadBut).

### Detection

```bash
rg -n 'shell=True' --type py
rg -n 'os\.system\(|os\.popen\(' --type py
rg -n "exec\(|execSync\(" --type ts | rg -v 'execFile'
rg -n 'exec\.Command\("sh"|exec\.Command\("bash"|exec\.Command\("/bin/sh"' --type go
```

---

## Use Safe Loaders for Deserialization

Use format-restricted loaders. For YAML: `safe_load`. For data exchange: JSON. Never use `pickle`, `marshal`, or `node-serialize` on untrusted input.

### Correct Pattern

**Python (YAML):**
```python
import yaml
config = yaml.safe_load(request.data)
```

**Python (data exchange):**
```python
import json
data = json.loads(request.data)
```

**Python (ML models):**
```python
from safetensors import safe_open
model = safe_open(uploaded_path, framework="pt")
```

**TypeScript:**
```ts
const data = JSON.parse(req.body);

import { z } from 'zod';
const Config = z.object({ name: z.string(), value: z.number() });
const validated = Config.parse(JSON.parse(req.body));
```

### Why This Matters

`pickle.loads` calls `__reduce__` which returns `(os.system, ("rm -rf /",))`. YAML default loader processes `!!python/object` tags. `node-serialize` calls `eval()`.

**CVEs:** CVE-2020-1747 (PyYAML FullLoader), CVE-2017-5941 (node-serialize), CVE-2021-44228 (Log4Shell), CVE-2022-22965 (Spring4Shell), Picklescan CVE-2025-1716.

### Detection

```bash
rg -n 'pickle\.loads|cloudpickle\.loads|joblib\.load|dill\.loads|marshal\.loads' --type py
rg -n 'yaml\.load\(' --type py | rg -v 'SafeLoader|safe_load'
rg -n 'node-serialize|\.unserialize\(' --type ts --type js
rg -n 'ObjectInputStream|readObject\(\)' --type java
```

---

## Render Templates from Files, Not from User Input

Template engines compile from trusted file paths. User-controlled template source = code execution sink.

### Correct Pattern

**Python (Flask/Jinja2):**
```python
@app.route("/preview")
def preview():
    return render_template("preview.html", body=request.args["body"])
```

**Python (Jinja2 direct):**
```python
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
tmpl = env.get_template("report.html")
output = tmpl.render(data=user_data)
```

**TypeScript (Handlebars):**
```ts
import { readFileSync } from 'fs';
import Handlebars from 'handlebars';
const tmpl = Handlebars.compile(readFileSync('views/preview.hbs', 'utf8'));
res.send(tmpl({ user: req.user }));
```

### Why This Matters

SSTI: `{{ config.__class__.__init__.__globals__['os'].popen('id').read() }}` executes commands.

**CVEs:** CVE-2019-10906 (Jinja2 sandbox escape), CVE-2016-10745 (Jinja2 bypass), CVE-2019-19919 (Handlebars prototype pollution RCE).

### Detection

```bash
rg -n 'render_template_string\(' --type py
rg -n 'Template\(.*request|Template\(.*user|Template\(.*data' --type py
rg -n 'Handlebars\.compile\(req\.|\.compile\(req\.body' --type ts --type js
rg -n 'pug\.compile\(|ejs\.render\(' --type ts --type js
```

---

## Evaluate Expressions with Restricted Parsers

Use restricted parsers for user expression evaluation. Never pass user strings to `eval`, `exec`, `Function`, or `vm`.

### Correct Pattern

**Python:**
```python
import ast
result = ast.literal_eval(request.args["expr"])

from simpleeval import simple_eval
result = simple_eval(request.args["expr"])
```

**TypeScript:**
```ts
import { evaluate } from 'mathjs';
const result = evaluate(userExpr, { scope: {} });
```

### Why This Matters

`eval` executes arbitrary code. Node's `vm` module is not a security sandbox — `vm2` was abandoned after CVE-2023-37903 proved it unfixable.

**CVEs:** CVE-2025-55182 (Next.js React2Shell), CVE-2023-37903/CVE-2023-29017/CVE-2023-32314 (vm2 escapes).

### Detection

```bash
rg -n 'eval\(|exec\(' --type py | rg -v 'ast\.literal_eval|# noqa'
rg -n 'eval\(|new Function\(|vm\.run' --type ts --type js
rg -n 'importlib\.import_module\(|__import__\(' --type py
rg -n 'eval\(|instance_eval|class_eval|send\(' --type ruby
```

---

## Validate Object Shape Before Deep Merge

Parse user objects through a schema validator before merging. Deep-merge allows prototype pollution: `{"__proto__": {"isAdmin": true}}`.

### Correct Pattern

**TypeScript:**
```ts
import { z } from 'zod';

const Config = z.object({
  theme: z.enum(['light', 'dark']).optional(),
  locale: z.string().max(5).optional(),
});

const validated = Config.parse(req.body);
const merged = { ...defaults, ...validated };
```

**When merge unavoidable:**
```ts
const config = Object.create(null);
for (const [key, value] of Object.entries(validated)) {
  config[key] = value;
}
```

### Why This Matters

Prototype pollution modifies `Object.prototype`, affecting every object in the process. Handlebars + lodash chain: pollute `helperMissing` via `_.merge`, then template compilation invokes the polluted helper.

**CVEs:** CVE-2019-10744 (lodash.merge), CVE-2020-8203 (lodash.zipObjectDeep), CVE-2019-11358 (jQuery.extend), CVE-2019-19919 (Handlebars RCE), CVE-2026-40175 (axios header injection via prototype pollution).

### Detection

```bash
rg -n '\.merge\(|\.mergeWith\(|\.defaultsDeep\(|\.set\(|\.setWith\(' --type ts --type js
rg -n '\$\.extend\(true' --type ts --type js
rg -n 'function.*merge|function.*deepMerge|function.*assign' --type ts --type js
```
