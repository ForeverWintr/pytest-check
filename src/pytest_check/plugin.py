import sys

import pytest
from _pytest._code.code import ExceptionInfo
from _pytest.skipping import xfailed_key
from _pytest.reports import ExceptionChainRepr
from _pytest._code.code import ExceptionRepr, ReprFileLocation

from . import check_log, check_raises, context_manager, pseudo_traceback


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    num_failures = check_log._num_failures
    failures = check_log.get_failures()
    check_log.clear_failures()

    if failures:
        if item._store[xfailed_key]:
            report.outcome = "skipped"
            report.wasxfail = item._store[xfailed_key].reason
        else:

            summary = f"Failed Checks: {num_failures}"
            longrepr = ["\n".join(failures)]
            longrepr.append("-" * 60)
            longrepr.append(summary)

            if report.longrepr:
                longrepr.append("-" * 60)
                longrepr.append(report.longreprtext)
                report.longrepr = "\n".join(longrepr)
            else:
                report.longrepr = "\n".join(longrepr)
            report.outcome = "failed"
            try:
                raise AssertionError(report.longrepr)
            except AssertionError as e:
                excinfo = ExceptionInfo.from_current()
                e_str = str(e)
                # will be 5 with color, 0 without
                if e_str.find('FAILURE: ') in (0, 5):
                    e_str = e_str.split('FAILURE: ')[1]
                reprcrash = ReprFileLocation(item.nodeid, 0, e_str)
                reprtraceback = ExceptionRepr(reprcrash, excinfo)
                chain_repr = ExceptionChainRepr([(reprtraceback, reprcrash, str(e))])
                report.longrepr = chain_repr

            call.excinfo = excinfo


def pytest_configure(config):
    # Add some red to the failure output, if stdout can accommodate it.
    isatty = sys.stdout.isatty()
    color = config.option.color
    check_log.should_use_color = (isatty and color == "auto") or (color == "yes")

    # If -x or --maxfail=1, then stop on the first failed check
    # Otherwise, let pytest stop on the maxfail-th test function failure
    maxfail = config.getvalue("maxfail")
    stop_on_fail = maxfail == 1

    # TODO: perhaps centralize where we're storing stop_on_fail
    context_manager._stop_on_fail = stop_on_fail
    check_raises._stop_on_fail = stop_on_fail
    check_log._stop_on_fail = stop_on_fail

    # Allow for --tb=no to turn off check's pseudo tbs
    traceback_style = config.getvalue("tbstyle")
    pseudo_traceback._traceback_style = traceback_style
    check_log._showlocals = config.getvalue('showlocals')

    # grab options
    check_log._default_max_fail = config.getoption("--check-max-fail")
    check_log._default_max_report = config.getoption("--check-max-report")
    check_log._default_max_tb = config.getoption("--check-max-tb")


# Allow for tests to grab "check" via fixture:
# def test_a(check):
#    check.equal(a, b)
@pytest.fixture(name="check")
def check_fixture():
    return context_manager.check


# add some options
def pytest_addoption(parser):
    parser.addoption(
        "--check-max-report",
        action="store",
        type=int,
        help="max failures to report",
    )
    parser.addoption(
        "--check-max-fail",
        action="store",
        type=int,
        help="max failures per test",
    )
    parser.addoption(
        "--check-max-tb",
        action="store",
        type=int,
        default=1,
        help="max pseudo-tracebacks per test",
    )
