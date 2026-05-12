#!/usr/bin/env bash
set -euo pipefail

NAME="simplenotes-gtk"
VERSION="1.2.0"
FLATPAK_ID="io.github.memugg64.SimpleNotesGTK"
BUILD_DIR="build/flatpak-build"
REPO_DIR="build/flatpak-repo"

rm -rf "${BUILD_DIR}" "${REPO_DIR}"

# Build
flatpak-builder --force-clean "${BUILD_DIR}" "flatpak/${FLATPAK_ID}.yml"

# Export to local repo
flatpak-builder --repo="${REPO_DIR}" --force-clean "${BUILD_DIR}" "flatpak/${FLATPAK_ID}.yml"

# Create bundle
flatpak build-bundle "${REPO_DIR}" "build/${NAME}_${VERSION}.flatpak" "${FLATPAK_ID}"

echo "Built: build/${NAME}_${VERSION}.flatpak"
