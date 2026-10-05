# Future server migration (outside V1)

MediaGrid V1 runs only on the user's Windows computer via localhost. This deployment
material is retained for a possible later phase and is not part of V1 setup.

This stack runs the panel, API, renderer worker, PostgreSQL and HTTPS reverse proxy on a
Linux server you control. It needs a domain name pointing to that server and inbound ports
80/443. For video rendering, start with at least 2 CPU cores, 4 GB RAM and 40 GB disk.
The database and output files live in Docker volumes; back them up before upgrades.
If you want to try a free server first, follow [FREE-ORACLE.md](FREE-ORACLE.md).

1. Obtain a Linux VPS and a domain or subdomain. Point its DNS A record to the VPS public IP.
2. Install Docker Engine with Compose, then clone this repository on the VPS.
3. Copy `deploy/.env.example` to `deploy/.env`. Set the domain and three unique secrets.
   Use letters and numbers only for `MEDIAGRID_DB_PASSWORD`, because it is part of a
   database URL. Do not commit or send secret values in chat.
4. Run `docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build`
   from the repository root.
5. Open `https://YOUR_DOMAIN` and sign in with `MEDIAGRID_ADMIN_PASSWORD`.

The stack refuses to start in public mode without an administrator password and session
signing secret. This does not publish content to social networks. The current renderer
creates text-based video; narration audio, verified research and licensed media still need
integration. A successful local build or saved cloud development environment does not make
the website public; the VPS, DNS and running stack are required before a public URL exists.
