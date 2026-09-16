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
        or not segment.path.endswith(".ts")
        or not {"start", "end", "contentlength"}.issubset(parse_qs(segment.query))
        or any(key not in range_keys and not key.startswith("qd_") for key in parse_qs(segment.query))
        or (parse_qs(segment.query).get("qd_tvid") not in (None, [str(target_tvid)]))
        for segment in segments
    ):
        return None
    sessions = {}
    schedules = []
    for url in observed_urls:
        parsed = urlsplit(url)
        if parsed.hostname == 'data.video.iqiyi.com':
            schedules.append(parsed)
    for observed_url in observed_urls:
        observed = urlsplit(observed_url)
        query = parse_qs(observed.query)
        if (observed.scheme not in ("http", "https") or not observed.hostname
                or observed.hostname == "data.video.iqiyi.com"
                or observed.path not in {segment.path for segment in segments}
                or query.get("qd_tvid") != [str(target_tvid)] or not query.get("qd_sc")):
            continue
        # The CDN may round ranges to block boundaries. In that case require
        # the exact player scheduling request with the same resource/signature.
        candidates = [observed] + [schedule for schedule in schedules
            if schedule.path == observed.path
            and parse_qs(schedule.query).get('qd_tvid') == [str(target_tvid)]
            and parse_qs(schedule.query).get('qd_sc') == query.get('qd_sc')]
        if not any(segment.path == candidate.path and all(parse_qs(candidate.query).get(key) == value
                   for key, value in parse_qs(segment.query).items() if key in {"start", "end", "contentlength"})
                   for segment in segments for candidate in candidates):
            continue
        sessions.setdefault(observed.path, observed)
    if any(segment.path not in sessions for segment in segments):
        return None
    rewritten = []
    for line in lines:
        if not line.strip() or line.startswith("#"):
            rewritten.append(line)
            continue
        segment = urlsplit(line.strip())
        observed = sessions[segment.path]
        params = dict(parse_qsl(observed.query))
        # CDN session parameters are issued by the player. Only the byte
        # range changes between fragments of the same physical resource.
        params.update((k, v) for k, v in parse_qsl(segment.query) if k in range_keys)
        rewritten.append(urlunsplit((observed.scheme, observed.netloc, segment.path,
                                    urlencode(params), "")))
    return "\n".join(rewritten) + "\n"


def missing_resource_seek(manifest, observed_urls, target_tvid):
    """Find the first unobserved resource and its playback start time."""
    elapsed = 0.0
    duration = 0.0
    resources = {}
    for line in manifest.splitlines():
        if line.startswith('#EXTINF:'):
            duration = float(line.split(':', 1)[1].split(',', 1)[0])
        elif line and not line.startswith('#'):
            path = urlsplit(line).path
            start = float(parse_qs(urlsplit(line).query).get('sd', [elapsed * 1000])[0]) / 1000
            resources.setdefault(path, (start, []))[1].append(line)
            elapsed += duration
    for path, (start, lines) in resources.items():
        single = '#EXTM3U\n' + ''.join('#EXTINF:1,\n' + line + '\n' for line in lines) + '#EXT-X-ENDLIST\n'
        if not resolve_browser_manifest(single, observed_urls, target_tvid):
            return path, start
    return None
