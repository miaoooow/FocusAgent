"""Instant local copy used before any model call."""

FALLBACK_PHRASES = {
    "mild": (
        "页面很忙，目标很凉",
        "手速在线，进度离线",
        "切页很快，成果等等",
        "计划在等，你先逛了",
        "目标没动，你挺忙",
    ),
    "spicy": (
        "摸鱼秒开，正事转圈",
        "进度条没动，你挺忙",
        "页面切得快，成果呢",
        "这波操作，目标没看懂",
        "猫币在掉，你还挺稳",
    ),
}


SUMMARY_FALLBACK_PHRASES = {
    "steady": (
        "这轮很稳，收工也有底气",
        "专注在线，今天顺利交卷",
    ),
    "recovered": (
        "有几次偏航，但你完成了",
        "中途走神，也还是走到了",
    ),
}
