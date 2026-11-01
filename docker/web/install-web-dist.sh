#!/bin/sh
# Installs the SPA bundle baked into this image (/dist) into the web_dist volume
# mounted at /srv/web:
#   /srv/web/releases/<WEB_RELEASE>/   one directory per deployed bundle
#   /srv/web/current -> releases/<WEB_RELEASE>   what Caddy serves (root)
# The copy lands under a temporary name and is renamed into place, and the
# `current` symlink is replaced with one rename, so a request never sees a
# partial tree. Re-running for an installed release only re-points `current`.
# Older releases are pruned, except the one that was current before (rollback:
# run this image again with the previous WEB_IMAGE tag).
#
# Bundles from the former on-droplet web-build sit at the volume root; they are
# left alone (Caddy no longer reads them) and can be deleted by hand.
set -eu

root=${WEB_ROOT:-/srv/web}
rel=${WEB_RELEASE:?WEB_RELEASE is not set}
target="$root/releases/$rel"

mkdir -p "$root/releases"

if [ -f "$target/index.html" ]; then
  echo "release $rel is already installed"
else
  rm -rf "$target.tmp"
  cp -a /dist "$target.tmp"
  mv -T "$target.tmp" "$target"
  echo "release $rel installed ($(du -sh "$target" | cut -f1))"
fi

prev=$(readlink "$root/current" 2>/dev/null || true)
ln -sfn "releases/$rel" "$root/current.tmp"
mv -fT "$root/current.tmp" "$root/current"
echo "current -> releases/$rel (was ${prev:-none})"

for dir in "$root"/releases/*/; do
  [ -d "$dir" ] || continue
  name=$(basename "$dir")
  [ "$name" = "$rel" ] && continue
  [ "releases/$name" = "$prev" ] && continue
  rm -rf "$dir"
  echo "pruned release $name"
done
