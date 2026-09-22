# Connection annex — Phase 3.1 visual fallback (TEMPLATE, placeholders only)

Placeholders only, never values. This mirrors the convention of `.env.paddle.example`: the shape is
committed so anyone can see what is needed, the filled-in copy is not.

**The real annex lives outside Git**, in the private working tree at
`extraction-shootout/private/PHASE3-FALLBACK-CONNECTION.md` on the machine that ran the shootout.
Ask Gustavo for it. Do not commit a filled-in copy of this file, and do not paste the address, port
or fingerprint into a report, a commit message, an issue or a handoff that lives in this repository.

The instance is rented and its address is ephemeral. Read it from the annex each time rather than
hard-coding it anywhere.

## The GPU host

| item | value |
|---|---|
| card | `<GPU model and memory>` |
| host CPU / RAM | `<vCPU count>`, `<RAM>` |
| disk | `<free space on /workspace>` |
| provider label | `<instance label>`, container hostname `<hostname>` |
| direct SSH | `ssh -p <PORT> root@<HOST>` |
| proxy SSH | `ssh -p <PROXY_PORT> root@<PROXY_HOST>` |
| host key (ED25519) | `SHA256:<FINGERPRINT>` |
| remote root | `/workspace/bank-statement-shootout` |

Verify the fingerprint on first connection. Never disable host-key checking. Never copy a private
key to the instance. Never ask anyone to send you a private key.

## Alias to add on the operator's computer (`~/.ssh/config`)

```
Host <ALIAS>
    HostName <HOST>
    Port <PORT>
    User root
    IdentityFile ~/.ssh/<KEY_NAME>
    IdentitiesOnly yes
```

## Ports

Port 8080 on the instance is the template's own Jupyter. Leave it alone. Model servers bind loopback
only and are reached through an SSH tunnel.

| service | port | tunnel |
|---|---|---|
| Stage A, the proposer | 18013 | `ssh <ALIAS> -L 127.0.0.1:18013:127.0.0.1:18013` |
| Stage B, the reviewer | 18022 | `ssh <ALIAS> -L 127.0.0.1:18022:127.0.0.1:18022` |

## What is installed on the instance

Recorded in full in section 2 of `PHASE3-VISUAL-FALLBACK.md`, which carries no connection details:
the `envs/vllm` serving environment, the CUDA 13 toolkit, both models at their pinned revisions, the
16 reference PDFs with their frozen 300 DPI renders, and the scripts in `tools/phase3_pair/`.

## The private working tree

Holds the run ledger, the original shootout handoff, this annex filled in, the backups of every
candidate's output, and the comparison package. Customer page content and detailed diffs stay there
and are never committed. Only counts, ratios and status reach this repository.
