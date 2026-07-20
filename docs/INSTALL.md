# Installing teagram-mini

> **Scaffold.** The full walkthrough comes with the first hosted release.

You need: a Jetson Orin Nano Dev Kit (8 GB) that you own, a screen or SSH
access, and a home network. Plan 45–60 minutes of active time, plus model
downloads. You bring your own Jetson and your own LLM.

- **Step 0 — Flash JetPack 7.2.** This step is required. The engine supports
  JetPack 7.2 / CUDA 13 only. Follow NVIDIA's flashing guide. We do not mirror
  JetPack.
- **Step 1 — Trim the desktop (recommended).** Run
  `sudo systemctl set-default multi-user.target` and reboot. Keep zram. Do not
  add an SD-card swap file.
- **Step 2 — Install NemoClaw.** This is NVIDIA's installer. Run it on your
  own terminal and give your own consent:
  `bash <(curl -fsSL https://www.nvidia.com/nemoclaw.sh)`.
- **Step 3 — Install teagram-mini.** Run
  `bash <(curl -fsSL https://get.teagram.co/mini)`.
- **Step 4 — Pair and talk.** Open the dashboard URL that the installer
  prints. Pair the device. Start a Talk session. If something looks wrong, run
  `teagram status` or `teagram doctor`.

TODO: expand each step; add troubleshooting, uninstall, and update paths.
