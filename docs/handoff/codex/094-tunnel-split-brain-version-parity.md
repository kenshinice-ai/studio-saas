# Tunnel split-brain/version parity
.venv/bin/python backend/scripts/verify_tunnel_parity.py \
  --local-base-url http://localhost:8901 \
  --public-base-url https://studiosaas.cc.cd \
  --expected-app-version 8.1.0 \
  --expected-mode saas

