# STANDING ORDERS

Persistent operating authority for the heartbeat loop. Each row is
condition → action → escalate. The Watcher evaluates these every heartbeat;
conditions are checked in code where possible and by the Watcher model where
judgment is needed. Actions still pass through the permission layer like any
other tool call.

| Condition | Action | Escalate? |
|---|---|---|
| Disk free space < 10% | Alert user via notification | Yes |
| CPU sustained > 90% for a full heartbeat | Note it in the log; alert if it persists two cycles | No |
| Scheduled task overdue > 24h | Remind user | No |
| Pending approval request older than 1h | Re-surface the approval to the user | No |
| Suspicious file-deletion request (mass/recursive/system paths) | Refuse, log, ask for confirmation | Yes |
| Audit log write failure | Halt autonomous actions until logging works again | Yes |
| Nothing needs attention | Log "heartbeat: nothing to do" and sleep | No |
