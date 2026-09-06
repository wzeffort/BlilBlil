"""Reuse a player route only when it serves an exact segment of our VOD."""
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit


def rebase_manifest(manifest, source_url, observed_url):
    lines = manifest.splitlines()
    if (not manifest.lstrip().startswith("#EXTM3U")
            or "#EXT-X-ENDLIST" not in lines
            or "#EXTINF:" not in manifest
            or any(line.startswith(("#EXT-X-KEY:", "#EXT-X-MAP:",
                                    "#EXT-X-BYTERANGE:", "#EXT-X-STREAM-INF:"))
                   for line in lines)):
        return None
    observed = urlsplit(observed_url)
    if observed.scheme not in ("https", "http") or not observed.hostname:
        return None
    segments = [urlsplit(urljoin(source_url, line.strip()))
                for line in lines if line.strip() and not line.startswith("#")]
    # A filename alone can match an advertisement or a different encode.
    # Require the same signed query, byte offsets, and segment index as well.
    query = dict(parse_qsl(observed.query))
    if not all(key in query for key in ("index", "brs", "bre", "token")):
        return None
    match = next((segment for segment in segments
                  if segment.path.rsplit("/", 1)[-1] == observed.path.rsplit("/", 1)[-1]
                  and sorted(parse_qsl(segment.query)) == sorted(parse_qsl(observed.query))), None)
    if match is None:
        return None
    old_directory = match.path.rsplit("/", 1)[0]
    if any(segment.netloc != match.netloc
           or segment.path.rsplit("/", 1)[0] != old_directory for segment in segments):
        return None
    directory = observed.path.rsplit("/", 1)[0]
    rewritten = []
    for line in lines:
        if not line.strip() or line.startswith("#"):
            rewritten.append(line)
            continue
        segment = urlsplit(urljoin(source_url, line.strip()))
        rewritten.append(urlunsplit((observed.scheme, observed.netloc,
                                    directory + "/" + segment.path.rsplit("/", 1)[-1],
                                    segment.query, "")))
    return "\n".join(rewritten) + "\n"
