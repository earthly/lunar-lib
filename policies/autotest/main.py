from lunar_policy import Check
import os

with Check("autotest-value-matches", "Autotest value matches filesystem") as c:            
    if not c.exists(".autotest.value"):
        c.fail("autotest value not collected")
