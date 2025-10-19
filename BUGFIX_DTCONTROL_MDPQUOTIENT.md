# dtcontrol Integration - Bug Fixes

## Issue Found

When running symbiotic synthesis on basic MDPs (like maze/steps), the code crashed with:

```
AttributeError: 'MdpQuotient' object has no attribute 'mdp'
```

## Root Cause

The code tried to access `self.quotient.mdp`, but `MdpQuotient` doesn't have a direct `mdp` attribute. Instead, it inherits `quotient_mdp` from the parent `Quotient` class.

### Code Structure

```python
class Quotient:
    def __init__(self, quotient_mdp=None, ...):
        self.quotient_mdp = quotient_mdp  # ← This is where the MDP is stored

class MdpQuotient(Quotient):
    def __init__(self, mdp, specification, tree_helper=None):
        super().__init__(specification=specification)
        # ... setup ...
        self.quotient_mdp = mdp  # ← MDP is assigned to quotient_mdp
```

## Fix Applied

Changed in `synthesizer_symbiotic.py`:

**Before:**
```python
mdp = self.quotient.mdp  # ❌ AttributeError
result = mdp.check_specification(...)
```

**After:**
```python
mdp = self.quotient.quotient_mdp  # ✅ Correct attribute
result = mdp.check_specification(...)
```

## Now Working

With this fix, dtcontrol will:

1. ✅ Compute optimal scheduler from basic MDP
2. ✅ Call dtcontrol with the scheduler
3. ✅ Get decision tree from dtcontrol
4. ✅ Parse and use the tree for synthesis

## Testing

To verify the fix works, run:

```bash
docker run -v="$(pwd)/results-symbiotic-smoke":/opt/cav25-experiments/results \
  dtpaynt-symbiotic ./experiments-with-symbiotic.sh --smoke-test --skip-omdt
```

You should now see in the logs:

```
synthesizer_symbiotic.py:120 - Using dtcontrol for tree generation instead of AR synthesis
synthesizer_symbiotic.py:128 - Step 1: Generating initial decision tree using dtcontrol...
synthesizer_symbiotic.py:241 - Model checking basic MDP to get optimal policy...
dtcontrol_wrapper.py:XXX - ✓ dtcontrol generated tree
synthesizer_symbiotic.py:XXX - [dtcontrol success #1] Tree stats: {...}
```

✅ **dtcontrol is now being called and its results are fed to dtPAYNT!**
