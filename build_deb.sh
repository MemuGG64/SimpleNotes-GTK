#!/usr/bin/env bash
set -euo pipefail

NAME="simplenotes-gtk"
VERSION="1.2.0"
ARCH="amd64"
PKG_DIR="build/${NAME}_${VERSION}_${ARCH}"

# Clean
rm -rf "build/${NAME}_${VERSION}_${ARCH}"
rm -f  "build/${NAME}_${VERSION}_${ARCH}.deb"

mkdir -p "${PKG_DIR}/DEBIAN"
mkdir -p "${PKG_DIR}/usr/bin"
mkdir -p "${PKG_DIR}/usr/share/applications"
mkdir -p "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${PKG_DIR}/usr/share/${NAME}/src"
mkdir -p "${PKG_DIR}/usr/share/${NAME}/resources"

# Control file
cat > "${PKG_DIR}/DEBIAN/control" << EOF
Package: ${NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: MemuGG64 <memugg64@users.noreply.github.com>
Description: Minimalist note-taking app
 A simple, fast note-taking application with support for text notes,
 to-do lists, markdown rendering, image embedding, and more.
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-pango-1.0, gir1.2-gdkpixbuf-2.0
EOF

# Wrapper script
cat > "${PKG_DIR}/usr/bin/${NAME}" << 'WRAPPER'
#!/usr/bin/env bash
exec /usr/bin/python3 /usr/share/simplenotes-gtk/SimpleNotes.py "$@"
WRAPPER
chmod +x "${PKG_DIR}/usr/bin/${NAME}"

# App files
cp SimpleNotes.py "${PKG_DIR}/usr/share/${NAME}/"
cp -r src/* "${PKG_DIR}/usr/share/${NAME}/src/"
cp resources/styles.css "${PKG_DIR}/usr/share/${NAME}/resources/"

# Desktop entry
cp resources/io.github.memugg64.SimpleNotesGTK.desktop "${PKG_DIR}/usr/share/applications/"

# Icon
cp resources/io.github.memugg64.SimpleNotesGTK.png \
   "${PKG_DIR}/usr/share/icons/hicolor/256x256/apps/"

# Build
fakeroot dpkg-deb --build "${PKG_DIR}" "build/${NAME}_${VERSION}_${ARCH}.deb"

echo "Built: build/${NAME}_${VERSION}_${ARCH}.deb"
