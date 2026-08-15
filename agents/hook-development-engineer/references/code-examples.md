# Hook Development Code Examples

Production-ready hook implementations with all safety patterns.

## Non-Blocking Hook Template

Complete template with comprehensive error handling and non-blocking execution.

```python
#!/usr/bin/env python3
"""
Hook template with non-blocking execution patterns.
Always exits with code 0 to prevent blocking Claude Code.
"""
import json
import sys
import traceback
from pathlib import Path
from datetime import datetime

def debug_log(message):
    """Log debug information without blocking execution."""
    try:
        with open('/tmp/claude_hook_debug.log', 'a') as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\n")
    except Exception:
        pass  # Never let logging block execution

def process_event(event_data):
    """
    Process the event and return result.

    Args:
        event_data: Parsed JSON from Claude Code event

    Returns:
        dict: Result to output (or None)
    """
    # Implement your hook logic here
    tool_name = event_data.get('tool', '')
    tool_output = event_data.get('output', '')

    debug_log(f"Processing {tool_name} event")

    # Example: Detect errors in tool output
    if 'error' in tool_output.lower():
        debug_log(f"Error detected in {tool_name}")
        return {'detected': True, 'tool': tool_name}

    return None

def main():
    """Main hook execution with comprehensive error handling."""
    try:
        # Parse input JSON from Claude Code
        input_data = json.loads(sys.stdin.read())

        # Process the event (implement specific logic here)
        result = process_event(input_data)

        # Output result if needed
        if result:
            print(json.dumps(result))

    except json.JSONDecodeError as e:
        debug_log(f"JSON parsing error: {e}")
    except Exception as e:
        debug_log(f"Unexpected error: {e}\\n{traceback.format_exc()}")
    finally:
        # CRITICAL: Always exit 0 to prevent blocking Claude Code
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Error Detection and Classification Hook

Complete PostToolUse hook with error pattern detection and learning database integration.

```python
#!/usr/bin/env python3
"""
Smart error detector with pattern matching and solution injection.
Detects errors, classifies them, queries learning database for solutions,
and injects high-confidence solutions into Claude Code context.
"""
import json
import sys
import hashlib
from pathlib import Path
from datetime import datetime

LEARNING_DB = Path.home() / '.claude' / 'learnings' / 'error_patterns.json'
DEBUG_LOG = Path('/tmp/claude_hook_debug.log')

def debug_log(message):
    """Non-blocking debug logging."""
    try:
        with DEBUG_LOG.open('a') as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\\n")
    except Exception:
        pass

def classify_error(tool_name, error_output):
    """
    Classify error type from tool output.

    Args:
        tool_name: Name of the tool that errored
        error_output: Error message from tool

    Returns:
        str: Error classification (missing_file, permissions, etc.)
    """
    output_lower = error_output.lower()

    # Classification rules
    if 'no such file' in output_lower or 'filenotfound' in output_lower:
        return 'missing_file'
    elif 'permission denied' in output_lower:
        return 'permissions'
    elif 'multiple matches' in output_lower and tool_name == 'Edit':
        return 'multiple_matches'
    elif 'syntaxerror' in output_lower:
        return 'syntax_error'
    elif 'typeerror' in output_lower:
        return 'type_error'
    else:
        return 'unknown'

def generate_signature(tool_name, error_type, error_message):
    """
    Generate unique signature for error pattern.

    Args:
        tool_name: Tool that produced error
        error_type: Classification of error
        error_message: Error message (first 200 chars)

    Returns:
        str: MD5 signature for pattern matching
    """
    # Use first 200 chars to avoid signature pollution from dynamic data
    message_snippet = error_message[:200]
    signature_input = f"{tool_name}:{error_type}:{message_snippet}"
    return hashlib.md5(signature_input.encode()).hexdigest()

def query_learning_db(signature):
    """
    Query learning database for known pattern.

    Args:
        signature: Error signature to lookup

    Returns:
        dict: Pattern data if found and high confidence (>0.7), else None
    """
    try:
        if not LEARNING_DB.exists():
            return None

        with LEARNING_DB.open('r') as f:
            data = json.load(f)

        patterns = data.get('patterns', [])
        for pattern in patterns:
            if pattern.get('signature') == signature:
                confidence = pattern.get('confidence', 0.0)
                if confidence > 0.7:  # High confidence threshold
                    return pattern

    except Exception as e:
        debug_log(f"Learning DB query error: {e}")

    return None

def inject_solution(solution_data, event_name: str) -> None:
    """
    Inject solution into Claude Code context via stdout.

    Args:
        solution_data: Solution dict with description and command
        event_name: Hook event name (e.g. "PostToolUse")
    """
    try:
        from hook_utils import context_output
        text = (
            f"[auto-fix] action={solution_data.get('command', '')}\n"
            f"description={solution_data.get('description', '')}\n"
            f"confidence={solution_data.get('confidence', 0.0)}"
        )
        context_output(event_name, text).print_and_exit()
    except Exception as e:
        debug_log(f"Context injection error: {e}")

def main():
    """Main error detection logic."""
    try:
        # Parse event JSON
        event = json.loads(sys.stdin.read())

        # Extract tool info
        tool_name = event.get('tool', '')
        tool_output = event.get('output', '')
        is_error = event.get('is_error', False)

        # Only process if error occurred
        if not is_error:
            sys.exit(0)

        debug_log(f"Error detected in {tool_name}")

        # Classify error
        error_type = classify_error(tool_name, tool_output)

        # Generate signature
        signature = generate_signature(tool_name, error_type, tool_output)

        # Query learning database
        pattern = query_learning_db(signature)

        # Inject solution if high confidence pattern found
        if pattern:
            inject_solution(pattern)
        else:
            debug_log(f"No high-confidence solution for {error_type} error")

    except Exception as e:
        debug_log(f"Fatal error: {e}")
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Learning Database Update Hook

Hook that tracks solution success/failure and updates confidence scores.

```python
#!/usr/bin/env python3
"""
Continuous learner hook that updates learning database based on outcomes.
Tracks solution application success/failure and adjusts confidence scores.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

LEARNING_DB = Path.home() / '.claude' / 'learnings' / 'error_patterns.json'
DEBUG_LOG = Path('/tmp/claude_hook_debug.log')

def debug_log(message):
    """Non-blocking debug logging."""
    try:
        with DEBUG_LOG.open('a') as f:
            f.write(f"[{datetime.now().isoformat()}] {message}\\n")
    except Exception:
        pass

def load_learning_db():
    """Load learning database with error handling."""
    try:
        if LEARNING_DB.exists():
            with LEARNING_DB.open('r') as f:
                return json.load(f)
    except Exception as e:
        debug_log(f"DB load error: {e}")

    # Return empty structure if load fails
    return {'patterns': [], 'metadata': {'version': '1.0'}}

def save_learning_db(data):
    """Save learning database with atomic operations."""
    try:
        # Ensure directory exists
        LEARNING_DB.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write pattern
        temp_path = LEARNING_DB.with_suffix('.tmp')
        with temp_path.open('w') as f:
            json.dump(data, f, indent=2)
        temp_path.replace(LEARNING_DB)

        debug_log("Learning DB updated successfully")

    except Exception as e:
        debug_log(f"DB save error: {e}")

def update_confidence(pattern_id, success):
    """
    Update confidence score for a pattern.

    Args:
        pattern_id: ID of pattern to update
        success: True if solution worked, False if failed
    """
    db = load_learning_db()

    for pattern in db['patterns']:
        if pattern.get('id') == pattern_id:
            current_confidence = pattern.get('confidence', 0.0)

            if success:
                # Increase confidence on success
                new_confidence = min(1.0, current_confidence + 0.1)
            else:
                # Decrease confidence on failure
                new_confidence = max(0.0, current_confidence - 0.2)

            pattern['confidence'] = new_confidence
            pattern['last_updated'] = datetime.now().isoformat()

            debug_log(f"Updated pattern {pattern_id}: {current_confidence} -> {new_confidence}")
            break

    save_learning_db(db)

def store_new_pattern(tool_name, error_type, signature, solution):
    """
    Store a new error pattern in learning database.

    Args:
        tool_name: Tool that produced error
        error_type: Classification of error
        signature: Unique error signature
        solution: Solution dict with description and command
    """
    db = load_learning_db()

    # Check if pattern already exists
    for pattern in db['patterns']:
        if pattern.get('signature') == signature:
            debug_log(f"Pattern {signature} already exists")
            return

    # Create new pattern with initial confidence 0.0
    new_pattern = {
        'id': f"{tool_name}_{error_type}_{len(db['patterns'])}",
        'tool': tool_name,
        'error_type': error_type,
        'signature': signature,
        'solution': solution,
        'confidence': 0.0,
        'created': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat()
    }

    db['patterns'].append(new_pattern)
    save_learning_db(db)

    debug_log(f"Stored new pattern: {new_pattern['id']}")

def main():
    """Main learning update logic."""
    try:
        # Parse event JSON
        event = json.loads(sys.stdin.read())

        # Check for learning update signals
        if 'pattern_id' in event and 'success' in event:
            # Update existing pattern confidence
            update_confidence(event['pattern_id'], event['success'])
        elif 'new_pattern' in event:
            # Store new pattern
            pattern_data = event['new_pattern']
            store_new_pattern(
                pattern_data['tool'],
                pattern_data['error_type'],
                pattern_data['signature'],
                pattern_data['solution']
            )

    except Exception as e:
        debug_log(f"Learning update error: {e}")
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Performance-Optimized Pattern Matching

Hook optimized for sub-50ms execution with lazy loading and early exit.

```python
#!/usr/bin/env python3
"""
Performance-optimized error pattern matcher.
Uses lazy loading and early exit to maintain sub-50ms execution time.
"""
import json
import sys
from pathlib import Path

LEARNING_DB = Path.home() / '.claude' / 'learnings' / 'error_patterns.json'

def find_pattern_lazy(signature, confidence_threshold=0.7):
    """
    Find pattern with lazy loading and early exit.

    Args:
        signature: Error signature to find
        confidence_threshold: Minimum confidence (default 0.7)

    Returns:
        dict: Pattern if found, else None
    """
    try:
        if not LEARNING_DB.exists():
            return None

        # Open file but don't load all at once
        with LEARNING_DB.open('r') as f:
            data = json.load(f)  # Unfortunately must load full JSON

            # But we can early-exit on first match
            for pattern in data.get('patterns', []):
                if pattern.get('signature') == signature:
                    if pattern.get('confidence', 0.0) >= confidence_threshold:
                        return pattern
                    else:
                        # Found pattern but confidence too low
                        return None

    except Exception:
        pass

    return None

def main():
    """Optimized pattern matching."""
    try:
        event = json.loads(sys.stdin.read())
        signature = event.get('signature')

        if signature:
            pattern = find_pattern_lazy(signature)
            if pattern:
                print(json.dumps({'found': True, 'pattern': pattern}))

    except Exception:
        pass
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()
```

---

## Hook Registration in settings.json

Complete settings.json configuration for hook registration.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "command": "python3",
        "args": ["/home/user/.claude/hooks/smart_error_detector.py"],
        "description": "Detects errors and injects learned solutions",
        "timeout": 50
      },
      {
        "command": "python3",
        "args": ["/home/user/.claude/hooks/continuous_learner.py"],
        "description": "Updates learning database with solution outcomes",
        "timeout": 50
      }
    ],
    "PreToolUse": [
      {
        "command": "python3",
        "args": ["/home/user/.claude/hooks/context_preparer.py"],
        "description": "Prepares context hints before tool execution",
        "timeout": 50
      }
    ],
    "SessionStart": [
      {
        "command": "python3",
        "args": ["/home/user/.claude/hooks/session_init.py"],
        "description": "Initializes learning database on session start",
        "timeout": 100,
        "once": true
      }
    ]
  }
}
```

**Key fields**:
- `command`: Python interpreter (python3)
- `args`: Full path to hook script
- `description`: Human-readable purpose
- `timeout`: Milliseconds before timeout (default 50ms for real-time hooks)
- `once`: Run only once per session (for SessionStart hooks)
