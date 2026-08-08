# Historical pregame snapshots

The production model must be trained on information that was actually available before each game.

Each snapshot stores:

- game and pitcher identity
- pregame feature payload
- source/version metadata
- capture timestamp
- eventual strikeout outcome
- optional batters-faced outcome
- immutable snapshot hash

Do **not** overwrite historical feature payloads with today's values. A later correction belongs to a new versioned snapshot.

## Training rule

A resolved snapshot is eligible for training only when its outcome is known. The feature payload remains frozen at its pregame state. Walk-forward evaluation must split snapshots chronologically; random train/test splitting is prohibited for production metrics.
