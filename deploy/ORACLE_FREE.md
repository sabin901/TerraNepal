# Full lab hosting: Oracle Always Free candidate

Checked 15 November 2026. No instance, account, domain or subscription has been created.
This is the selected candidate, conditional on the owner's account eligibility and capacity.

## Fit and constraints

The application needs one web process and one background worker sharing a persistent
local filesystem. Keep the current Docker Compose layout, authentication and Caddy TLS.
Use an Always Free eligible Ampere A1 instance only after the console confirms its
shape, memory, boot/block storage and network configuration incur no charges. Current
Oracle documentation describes 2 OCPUs / 12 GB total for eligible A1 free resources;
check the actual tenancy entitlement before creation. Do not use trial credit as proof
of ongoing free eligibility. The existing suggested minimum is 2 CPUs, 8 GB RAM and
20 GB free disk; measure the archive and backups before selecting storage.

Signup requires owner-completed identity/card verification. Capacity may be unavailable;
idle resources may be reclaimed. This is a research-hosting option, not guaranteed
emergency infrastructure. Preserve independent off-host backups. Do not generate fake
load to evade reclamation policies.

Render's free web tier has no persistent disk and is not a compatible drop-in host for
this SQLite/archive application. Rewriting storage would be a separate migration.

## Owner prerequisites

1. Complete Oracle signup privately and confirm Always Free capacity in the home region.
2. Provision an eligible Linux A1 VM and persistent storage; do not enable paid extras.
3. Configure owner-controlled SSH access. Provide only an SSH alias/hostname to the agent,
   never a private key or password in chat. ARM container compatibility must pass on host.
4. Supply a hostname you control pointing to the VM for HTTPS. Domain purchase is not
   authorized or included; a suitable existing hostname is sufficient.
5. Restrict SSH to operator access; expose only 80/443 for the app. Never expose 8765 or
   database files. Apply both cloud-network and host firewall rules.

## Application deployment

Follow `disaster_lab/DEPLOYMENT.md`, "First remote deployment", including verified
snapshot transfer/restore, UID 10001 ownership, interactive owner-password setup,
image build, startup and acceptance tests. Do not transfer credentials from the laptop.
Private archive data is transferred only to the selected owner-controlled host.
The public Pages dashboard remains available independently.

## Remote acceptance evidence still required

- Image builds and runs on the selected host architecture.
- TLS certificate and hostname validation succeed without bypasses.
- Anonymous private API access is denied; authenticated workspace and CSRF work.
- Worker completes permitted collection/analysis jobs; source failures remain visible.
- Archive, cases and notebook survive service and host restarts.
- Backup restores to a separate destination with hashes verified.
- Memory, free disk, collection latency and growth are measured on real data.
- Report includes release SHA, host architecture, check times and failures without secrets.

A successful GitHub container test does not replace these host-specific checks.

Sources:
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://www.oracle.com/cloud/free/faq/
- https://render.com/docs/free
