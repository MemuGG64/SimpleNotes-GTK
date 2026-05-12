#!/usr/bin/env bash
set -euo pipefail

NAME="simplenotes-gtk"
VERSION="1.2.0"
REPO="https://github.com/MemuGG64/SimpleNotes-GTK"
PAGES_DIR="gh-pages"

# ── 1. Build packages ──────────────────────────────────────────
bash build_deb.sh
bash build_flatpak.sh

# ── 2. Prepare gh-pages directory ──────────────────────────────
rm -rf "${PAGES_DIR}"
mkdir -p "${PAGES_DIR}/apt"
mkdir -p "${PAGES_DIR}/flatpak"

# ── 3. Copy packages ───────────────────────────────────────────
cp "build/${NAME}_${VERSION}_amd64.deb" "${PAGES_DIR}/apt/"
cp "build/${NAME}_${VERSION}.flatpak"   "${PAGES_DIR}/flatpak/"

# ── 4. Create Flatpak repo ─────────────────────────────────────
cp -r build/flatpak-repo/* "${PAGES_DIR}/flatpak/"
# Generate static repo metadata (for direct hosting without flatpak-builder --repo)
flatpak build-update-repo "${PAGES_DIR}/flatpak" --generate-static-deltas 2>/dev/null || true

# ── 5. Create APT repo ─────────────────────────────────────────
cd "${PAGES_DIR}/apt"

# Generate Packages
dpkg-scanpackages --multiversion . /dev/null > Packages 2>/dev/null
gzip -9kf Packages

# Generate Release
cat > Release << EOF
Origin: SimpleNotes-GTK
Label: SimpleNotes-GTK APT Repository
Suite: stable
Codename: stable
Date: $(date -Ru)
Architectures: amd64
Components: main
Description: APT repository for SimpleNotes-GTK
EOF

# Check / generate GPG key
GPG_KEY_NAME="SimpleNotes-GTK (APT signing key)"
GPG_KEY_EMAIL="memugg64@users.noreply.github.com"

if ! gpg --list-keys "${GPG_KEY_EMAIL}" &>/dev/null; then
    echo "No GPG key found — generating one non-interactively..."
    gpg --batch --gen-key << EOF
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: ${GPG_KEY_NAME}
Name-Email: ${GPG_KEY_EMAIL}
Expire-Date: 0
%no-protection
%commit
EOF
fi

# Export the public key for users
gpg --armor --export "${GPG_KEY_EMAIL}" > ../simplenotes-archive-keyring.gpg

# Sign Release
gpg --batch --yes --armor --detach-sign --output Release.gpg Release
gpg --batch --yes --armor --detach-sign --output InRelease Release

cd ../..

# ── 6. Create install instructions ─────────────────────────────
cat > "${PAGES_DIR}/index.html" << 'HTML'
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>SimpleNotes-GTK</title></head>
<body style="font-family:sans-serif;max-width:800px;margin:auto;padding:2em">
<h1>SimpleNotes-GTK</h1>
<p>Minimalist note-taking app v1.2.0</p>

<h2>APT install</h2>
<pre><code>sudo mkdir -p /usr/share/keyrings
sudo wget -O /usr/share/keyrings/simplenotes-archive-keyring.gpg \
  https://memugg64.github.io/SimpleNotes-GTK/simplenotes-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/simplenotes-archive-keyring.gpg] https://memugg64.github.io/SimpleNotes-GTK/apt ./" | \
  sudo tee /etc/apt/sources.list.d/simplenotes.list
sudo apt update
sudo apt install simplenotes-gtk</code></pre>

<h2>Flatpak install</h2>
<pre><code>flatpak remote-add --user --if-not-exists simplenotes \
  https://memugg64.github.io/SimpleNotes-GTK/flatpak
flatpak install --user simplenotes io.github.memugg64.SimpleNotesGTK</code></pre>

<h2>Updating</h2>
<ul>
  <li><strong>APT:</strong> <code>sudo apt update && sudo apt upgrade</code></li>
  <li><strong>Flatpak:</strong> <code>flatpak update</code></li>
</ul>
</body></html>
HTML

echo "────────────────────────────────────────────"
echo "Packages ready in ./${PAGES_DIR}/"
echo ""
echo "To publish, run:"
echo "  git checkout --orphan gh-pages"
echo "  rm -rf *"
echo "  mv ${PAGES_DIR}/* ."
echo "  rmdir ${PAGES_DIR}"
echo "  git add . && git commit -m 'Publish v${VERSION}'"
echo "  git push origin gh-pages"
echo ""
echo "Then users can install via APT or Flatpak (see index.html)"
echo "────────────────────────────────────────────"
