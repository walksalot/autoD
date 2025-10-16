# Model Policy (v2024-09-23)

This repository uses a shared model policy so every human and automated agent
picks the same OpenAI/Anthropic models without accidentally reverting to older
generations.

## Approved model IDs

| Purpose | Model ID |
| ------- | -------- |
| Primary multimodal metadata extraction | `gpt-5` |
| Fallback / cost-aware passes | `gpt-5-mini` |
| Anthropic parity / cross-checks | `claude-4.5-sonnet` |

All runtime code must import these identifiers from `config.models`. Do **not**
inline model strings in scripts or tests.

## Prohibited model IDs

Do not reference legacy deployments (e.g., `gpt-4`, `gpt-3.5-turbo`,
`claude-3.5-sonnet`, `claude-3-opus`). The lint/test tooling will fail if those
appear in diffs. If a downstream SDK defaults to an older model, override it
explicitly with an approved ID.

## Change control

1. Discuss the new model with the platform/infra owners.
2. Update `config/models.py` (bump `MODEL_POLICY_VERSION`, adjust allow list).
3. Update this file and circulate the change in the release notes or team chat.
4. Run `python scripts/check_model_policy.py --diff` and `pytest` locally; both
   should succeed before opening a pull request.

Agents with older training data must **stop** and request guidance if they need
an unlisted model. Automated changes to `config/models.py` require explicit
approval.
