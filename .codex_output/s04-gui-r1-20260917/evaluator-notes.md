# GUI r1 evaluator notes

- Generation: fresh CLI thread `01a0ad6a-2fda-7273-9135-4c054a9af0d0`, no resume/history supplied.
- Supplied files are copied documentation, official reference client/examples, schemas, configuration models,
  statusword definitions and actual isolated Mock config. This is not a no-example generation evaluation.
- Mock endpoint: 127.0.0.1:52728. User's manual test server is not used or terminated.
- Manual settings snapshot preserved in manual-settings-reference.json. Larger distances/speeds applied to prompt.
- Generation budget: no added time/token deadline.
- Baseline infrastructure check: existing reference GUI close-during-wait test passed (3.654s suite time).
  First invocation also used the wrong class for delay test (AttributeError, evaluator invocation error).
  Correct DelayedResponseTests.test_gui_stop_responsive_while_move_response_is_delayed then passed (4.491s).
- Baseline tests are not evidence that the newly generated GUI passes. No Teaching or Node-RED tests run.
- Planned independent assessment: normal sequence/GUI authority retention, duplicate Run, Stop,
  window close while running, input timeout/API Fail, response-delay responsiveness, connection/authority
  loss and runtime Fault. Assess actual emitted requests, outputs, positions and GUI state.
- Deterministic test runs use no additional model calls. Evaluator conversation usage excluded from generation tally.
