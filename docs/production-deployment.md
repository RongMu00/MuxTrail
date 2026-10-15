# Production deployment

Production deployment starts only after the `CI` workflow succeeds for a push to `main`:

```text
push main
  -> backend and frontend CI
  -> build the production frontend
  -> update and health-check the GCE backend
  -> publish the frontend to GitHub Pages
```

Pull request runs and failed CI runs never deploy. The backend keeps its existing `.env` and
Cloudflare Tunnel configuration because neither file is tracked by Git.

## One-time GCE setup

Create a dedicated deployment key on the computer used to administer the project:

```bash
ssh-keygen -t ed25519 -C github-actions-muxtrail -f ~/.ssh/muxtrail_github_actions
```

Do not enter a passphrase because the key is used non-interactively. Copy only the public key to
the GCE user's `~/.ssh/authorized_keys`. Keep the private key out of the repository.

Confirm that the deployment user can run these commands on the VM without a password prompt:

```bash
cd ~/MuxTrail
git fetch origin main
sudo systemctl restart muxtrail
sudo systemctl is-active muxtrail
```

If `sudo` asks for a password, grant only the two commands used by deployment:

```bash
printf '%s\n' \
  'rongmu0918 ALL=(root) NOPASSWD: /usr/bin/systemctl restart muxtrail' \
  'rongmu0918 ALL=(root) NOPASSWD: /usr/bin/journalctl -u muxtrail -n 50 --no-pager' \
  | sudo tee /etc/sudoers.d/muxtrail-deploy > /dev/null
sudo chmod 440 /etc/sudoers.d/muxtrail-deploy
sudo visudo -cf /etc/sudoers.d/muxtrail-deploy
```

The repository directory must contain the production virtual environment at `.venv`, and the
systemd service must be named `muxtrail`.

## GitHub production environment

In the repository, open **Settings -> Environments**, create an environment named `production`,
and restrict its deployment branch to `main`. Do not enable required reviewers if deployment
should remain automatic.

Add these environment secrets:

| Name | Value |
|---|---|
| `GCE_HOST` | The VM's static external IPv4 address or resolvable SSH hostname |
| `GCE_SSH_PRIVATE_KEY` | Complete contents of `~/.ssh/muxtrail_github_actions` |
| `GCE_SSH_KNOWN_HOSTS` | Trusted SSH host-key line for the VM |

Obtain the trusted host key while connected through the Google Cloud SSH console:

```bash
sudo ssh-keygen -y -f /etc/ssh/ssh_host_ed25519_key
```

Store it as the `GCE_SSH_KNOWN_HOSTS` secret in this format, replacing the address and key:

```text
203.0.113.10 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAA...
```

Add these environment variables:

| Name | Example |
|---|---|
| `GCE_USER` | `rongmu0918` |
| `GCE_APP_DIR` | `/home/rongmu0918/MuxTrail` |

The VM firewall must allow SSH from GitHub-hosted runners. The application port remains bound to
loopback and is still published only through Cloudflare Tunnel.

## Failure behavior

- Failed CI: neither backend nor frontend deploys.
- Failed frontend build: neither backend nor frontend deploys.
- Failed backend update or health check: GitHub Pages is not updated.
- Successful backend health check: the exact tested commit is published to GitHub Pages.

Deployment uses `git merge --ff-only`, so unexpected server-side tracked changes cause a safe
failure instead of being overwritten.
