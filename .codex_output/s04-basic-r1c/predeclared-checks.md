# Basic case r1b independent checks (before submission)

Generated CLI, no Teaching/GUI. Source Mock per scenario; preinitialized/homed/enabled externally.
Same requested coordinates/velocities and common acceleration; endpoint changed only for test isolation.
Do not edit submitted Python. If configurable timeouts are absent, use the prompt's actual values.

- Normal: exactly two axes moves to Pick then Place, velocities [5,5,2], profile [100,100] once per axis.
  Position/reached/standstill observed before respective output writes, grasp values true/100,
  no Place until DI true AND AI>=50, release false/0, Stop then release authority, exit success.
- Input timeout: DI/AI remain false/0; no Place/release outputs; failure, Stop and output retention.
- API Fail: evaluator disables one axis before Run; server rejection, no outputs/next move, failure.
- Stop: SIGINT during input wait; no Place, cleanup stop/authority release, no disable.
- Runtime Fault: test-launcher WKC=0 after grasp; server Fault feedback, no Place, failure; no fake stop.
- Connection loss: proxy drops connection during input wait; bounded failure, no replay/authority retry.
- Authority loss: evaluator transfers/revokes ownership using supported test access if available;
  otherwise mark blocked/not tested, not success.
- Response timeout: proxy delays first move Success six seconds (>request timeout five seconds),
  no outputs/Place, Stop attempt; late response does not resume program.
- Schema validate observed requests; read code for feedback freshness, no server interlock duplication,
  no command wrapper framework, no unsafe auto recovery/homing/enable/disable.

All applicable criteria required; artifact self-tests alone are not independent proof.
Errors in test harness are recorded and corrected without modifying submission.
