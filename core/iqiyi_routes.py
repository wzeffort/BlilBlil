"""Resolve iQiyi's byte-range playlist using its observed player CDN session."""
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit, urlunsplit


def resolve_browser_manifest(manifest, observed_urls, target_tvid):
    lines = manifest.splitlines()
    if (not manifest.lstrip().startswith("#EXTM3U") or "#EXT-X-ENDLIST" not in lines
            or "#EXTINF:" not in manifest
            or any(line.startswith(("#EXT-X-KEY:", "#EXT-X-MAP:", "#EXT-X-BYTERANGE:")) for line in lines)):
        return None
    segments = [urlsplit(line.strip()) for line in lines if line.strip() and not line.startswith("#")]
    range_keys = {"start", "end", "contentlength", "sd"}
    if not segments or any(
        segment.hostname != "data.video.iqiyi.com"
        or segment.path != segments[0].path
        or not segment.path.endswith(".ts")
        or not {"start", "end", "contentlength"}.issubset(parse_qs(segment.query))
        or not set(parse_qs(segment.query)).issubset(range_keys)
        for segment in segments
    ):
        return None
    for observed_url in observed_urls:
        observed = urlsplit(observed_url)
        query = parse_qs(observed.query)
        if (observed.scheme not in ("http", "https") or not observed.hostname
                or observed.hostname == "data.video.iqiyi.com"
                or observed.path != segments[0].path
                or query.get("qd_tvid") != [str(target_tvid)] or not query.get("qd_sc")):
            continue
        if not any(all(query.get(key) == value for key, value in parse_qs(segment.query).items())
                   for segment in segments):
            continue
        rewritten = []
        for line in lines:
            if not line.strip() or line.startswith("#"):
                rewritten.append(line)
                continue
            segment = urlsplit(line.strip())
            params = dict(parse_qsl(observed.query))
            params.update(parse_qsl(segment.query))
            rewritten.append(urlunsplit((observed.scheme, observed.netloc, segment.path,
                                        urlencode(params), "")))
        return "\n".join(rewritten) + "\n"
    return None
