def promotion_allowed(
    health_ok: bool,
    regression_tests_ok: bool,
    security_checks_ok: bool,
) -> bool:
    return health_ok and regression_tests_ok and security_checks_ok
