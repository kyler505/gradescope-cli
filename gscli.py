from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

from gradescopeapi.classes.connection import GSConnection
from gradescopeapi.classes.submission import upload_assignment


def load_credentials(
    auth_path: Path | None = None, interactive: bool = True
) -> tuple[str, str]:
    if auth_path and auth_path.exists():
        lines = [line.strip() for line in auth_path.read_text().splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
    if interactive:
        import getpass

        email = input("Enter Gradescope email: ").strip()
        password = getpass.getpass("Enter password: ")
        return email, password
    raise ValueError("No credentials provided or found")


def serialize_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if hasattr(value, "__dict__"):
        data = {
            key: serialize_value(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
        if data:
            return data
    return repr(value)


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_datetime(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    if parsed is None:
        return "None" if value is None else str(value)
    return parsed.strftime("%Y-%m-%d %H:%M %z")


def login_connection(
    email: str | None = None, password: str | None = None
) -> tuple[str, GSConnection]:
    auth_path = Path(__file__).with_name("auth.txt")
    if email is None or password is None:
        email, password = load_credentials(auth_path)
    connection = GSConnection()
    print(f"Logging in as {email}...", file=sys.stderr)
    connection.login(email, password)
    return email, connection




def extract_submission_id(url: str) -> str | None:
    if "/submissions/" not in url:
        return None
    return url.split("/submissions/")[-1].split("?")[0].split("#")[0]


def get_latest_submission_id(session, course_id: str, assignment_id: str) -> str:
    assign_url = f"https://gradescope.com/courses/{course_id}/assignments/{assignment_id}"
    resp = session.get(assign_url, allow_redirects=True)
    resp.raise_for_status()

    sub_id = extract_submission_id(resp.url)
    if not sub_id:
        raise RuntimeError("No submission found for this assignment")
    return sub_id


def get_submission_json(
    session,
    course_id: str,
    assignment_id: str,
    submission_id: str,
    only_keys: list[str] | None = None,
) -> dict[str, Any]:
    json_url = (
        f"https://gradescope.com/courses/{course_id}/assignments/{assignment_id}"
        f"/submissions/{submission_id}.json?content=react"
    )
    if only_keys:
        keys_qs = "&".join(f"only_keys[]={key}" for key in only_keys)
        json_url = f"{json_url}&{keys_qs}"

    resp = session.get(json_url)
    if resp.status_code != 200:
        raise RuntimeError(f"Submission request failed: HTTP {resp.status_code}")
    return resp.json()


def render_autograder_results(
    data: dict[str, Any],
    course_id: str,
    assignment_id: str,
    failed_only: bool = False,
    show_stdout: bool = False,
) -> int:
    ag = data.get("autograder_results") or {}
    submission = data.get("assignment_submission") or {}
    assignment_info = data.get("assignment") or {}

    print("\n=== Autograder Results ===\n")
    title = assignment_info.get("title", "Unknown")
    print(f"  Assignment: {title} (ID: {assignment_id})")
    print(f"  Course: {course_id}")
    print(f"  Status: {submission.get('status', 'Unknown')}")
    print(f"  Score: {ag.get('score', 'N/A')}")
    print(f"  Submission time: {submission.get('created_at', 'Unknown')}")

    output_msg = ag.get("output")
    if output_msg:
        print(f"\n  Message: {output_msg}")

    tests = ag.get("tests", [])
    if tests:
        passed = sum(1 for t in tests if t.get("status") == "passed")
        failed = sum(1 for t in tests if t.get("status") == "failed")
        errored = sum(1 for t in tests if t.get("status") == "error")
        total_max = sum(t.get("max_score", 0) for t in tests)

        print(f"\n  Tests: {passed} passed, {failed} failed, {errored} errored ({len(tests)} total)")
        print(f"  Total: {ag.get('score', 0)} / {total_max}\n")

        if failed_only:
            tests_to_show = [t for t in tests if t.get("status") != "passed"]
            if not tests_to_show:
                print("  All tests passed!")
                return 0
        else:
            tests_to_show = tests

        for test in tests_to_show:
            status_icon = "✓" if test.get("status") == "passed" else "✗"
            score_str = f"{test.get('score', 0)}/{test.get('max_score', 0)}"
            print(f"  {status_icon} [{test.get('number', '?')}] {test.get('name', 'Unknown')}  ({score_str})")
            test_output = test.get("output")
            if test_output:
                for line in test_output.strip().splitlines():
                    print(f"    │ {line}")
    else:
        no_ag_msg = ag.get("output", "")
        if "autograder" in no_ag_msg.lower():
            print(f"\n  {no_ag_msg}")
            return 0
        print("\n  No test results available.")

    stdout = ag.get("stdout")
    if stdout and ag.get("stdout_shown_to_students"):
        if show_stdout:
            print("\n  === Autograder Stdout ===\n")
            for line in stdout.splitlines():
                print(f"    {line}")
        else:
            print("\n  (Autograder stdout available — use --show-stdout to display)")

    error_code = ag.get("error_code")
    if error_code:
        print(f"\n  ⚠ Error code: {error_code}")

    return 0

def get_courses(connection: GSConnection) -> dict[str, dict[str, dict[str, Any]]]:
    account = connection.account
    if account is None:
        raise RuntimeError("Login did not create an account session")
    return serialize_value(account.get_courses())


def get_assignments(connection: GSConnection, course_id: str) -> list[dict[str, Any]]:
    account = connection.account
    if account is None:
        raise RuntimeError("Login did not create an account session")
    assignments = serialize_value(account.get_assignments(course_id))
    assignment_list = assignments if isinstance(assignments, list) else [assignments]
    for assignment in assignment_list:
        assignment["open"] = is_assignment_open(assignment)
    return assignment_list


def get_course_lookup(courses: dict[str, dict[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for role in ("student", "instructor"):
        for course_id, course in (courses.get(role) or {}).items():
            lookup[course_id] = {**course, "role": role}
    return lookup


def is_assignment_open(assignment: dict[str, Any]) -> bool:
    now = datetime.now().astimezone()
    release = parse_iso_datetime(assignment.get("release_date"))
    due = parse_iso_datetime(assignment.get("due_date"))
    late_due = parse_iso_datetime(assignment.get("late_due_date"))
    if release and now < release:
        return False
    deadline = late_due or due
    if deadline and now > deadline:
        return False
    return True


def format_course(course_id: str, course: dict[str, Any]) -> str:
    name = course.get("name", "Unknown")
    full_name = course.get("full_name", "")
    return f"{course_id}: {name} - {full_name}"


def format_assignment_brief(assignment: dict[str, Any]) -> str:
    assignment_id = assignment.get("assignment_id", "??")
    name = assignment.get("name", "Unknown")
    due = format_datetime(assignment.get("due_date"))
    return f"{assignment_id}: {name} | due {due} | open={assignment.get('open', False)}"


def collect_deadlines(
    connection: GSConnection, course_ids: list[str] | None = None, open_only: bool = True
) -> list[dict[str, Any]]:
    courses = get_courses(connection)
    course_lookup = get_course_lookup(courses)
    target_ids = course_ids or list(course_lookup.keys())
    deadlines: list[dict[str, Any]] = []
    for course_id in target_ids:
        course = course_lookup.get(course_id)
        if course is None:
            raise ValueError(f"Unknown course ID: {course_id}")
        for assignment in get_assignments(connection, course_id):
            if open_only and not assignment.get("open"):
                continue
            deadlines.append(
                {
                    "course_id": course_id,
                    "course_name": course.get("name", "Unknown"),
                    "course_role": course.get("role", "unknown"),
                    **assignment,
                }
            )
    def deadline_sort_key(item: dict[str, Any]) -> tuple[bool, float, str, str]:
        parsed_due = parse_iso_datetime(item.get("due_date"))
        due_value = parsed_due.timestamp() if parsed_due else float("inf")
        return (
            parsed_due is None,
            due_value,
            item.get("course_name", ""),
            item.get("name", ""),
        )

    deadlines.sort(key=deadline_sort_key)
    return deadlines


def cmd_courses(args: argparse.Namespace) -> int:
    try:
        _, connection = login_connection(args.email, args.password)
        courses = get_courses(connection)
    except Exception as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1

    print("\n=== Courses ===")
    print("\nInstructor:")
    for course_id, course in (courses.get("instructor") or {}).items():
        print("  " + format_course(course_id, course))
    print("\nStudent:")
    for course_id, course in (courses.get("student") or {}).items():
        print("  " + format_course(course_id, course))
    return 0


def cmd_assignments(args: argparse.Namespace) -> int:
    try:
        _, connection = login_connection(args.email, args.password)
        assignments = get_assignments(connection, args.course_id)
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    if args.open_only:
        assignments = [assignment for assignment in assignments if assignment.get("open")]

    print(f"\n=== Assignments (course {args.course_id}) ===\n")
    for assignment in assignments:
        print("  " + format_assignment_brief(assignment))
        print(f"    Release: {format_datetime(assignment.get('release_date'))}")
        print(f"    Due: {format_datetime(assignment.get('due_date'))}")
        print(f"    Late Due: {format_datetime(assignment.get('late_due_date'))}")
        print(f"    Status: {assignment.get('submissions_status')}")
        print(f"    Score: {assignment.get('grade')} / {assignment.get('max_grade')}")
        print()

    if not assignments:
        print("  No assignments matched.")
    return 0


def cmd_submit_assignment(args: argparse.Namespace) -> int:
    files = [Path(path).expanduser() for path in args.files]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        print("These files do not exist:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Dry run: would upload these files:")
        for path in files:
            print(f"  {path}")
        print(f"Course: {args.course_id}")
        print(f"Assignment: {args.assignment_id}")
        if args.leaderboard_name:
            print(f"Leaderboard name: {args.leaderboard_name}")
        return 0

    handles = []
    try:
        _, connection = login_connection(args.email, args.password)
        for path in files:
            handles.append(path.open("rb"))
        submission_url = upload_assignment(
            connection.session,
            args.course_id,
            args.assignment_id,
            *handles,
            leaderboard_name=args.leaderboard_name,
        )
    except Exception as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        return 1
    finally:
        for handle in handles:
            handle.close()

    if not submission_url:
        print(
            "Upload did not return a submission URL. Gradescope likely rejected the submission or redirected back to the course page.",
            file=sys.stderr,
        )
        return 1

    print("Submission created:")
    print(f"  {submission_url}")

    # Extract submission ID from URL for --wait
    if hasattr(args, "wait") and args.wait:
        if "/submissions/" in submission_url:
            sub_id = submission_url.split("/submissions/")[-1].split("?")[0].split("#")[0]
            print("\nWaiting for autograder to finish...\n")
            try:
                poll_autograder_status(
                    connection.session, args.course_id, args.assignment_id, sub_id,
                    interval=args.interval, timeout=args.timeout
                )
            except TimeoutError as exc:
                print(f"\n{exc}", file=sys.stderr)
                print("Check results later with: gscli.py view-results -c {} -a {}".format(
                    args.course_id, args.assignment_id
                ))
                return 1

            # Clear progress line and show final results using the same authenticated session
            print(" " * 80, end="\r")
            try:
                data = get_autograder_results(
                    connection,
                    args.course_id,
                    args.assignment_id,
                    submission_id=sub_id,
                )
            except Exception as exc:
                print(f"Failed to fetch final results: {exc}", file=sys.stderr)
                return 1

            return render_autograder_results(
                data,
                course_id=args.course_id,
                assignment_id=args.assignment_id,
                failed_only=args.failed_only,
                show_stdout=args.show_stdout,
            )

    return 0


def cmd_deadlines(args: argparse.Namespace) -> int:
    try:
        _, connection = login_connection(args.email, args.password)
        deadlines = collect_deadlines(
            connection,
            course_ids=args.course_id,
            open_only=not args.include_closed,
        )
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    if args.limit is not None:
        deadlines = deadlines[: args.limit]

    print("\n=== Deadlines ===\n")
    for item in deadlines:
        print(
            f"  [{item['course_name']}] {item.get('assignment_id', '??')}: {item.get('name', 'Unknown')}"
        )
        print(f"    Course ID: {item['course_id']} ({item['course_role']})")
        print(f"    Due: {format_datetime(item.get('due_date'))}")
        print(f"    Open: {item.get('open', False)}")
        print()

    if not deadlines:
        print("  No matching assignments found.")
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    try:
        email, connection = login_connection(args.email, args.password)
        courses = get_courses(connection)
    except Exception as exc:
        print(f"Login failed: {exc}", file=sys.stderr)
        return 1

    student_courses = courses.get("student") or {}
    instructor_courses = courses.get("instructor") or {}
    print("\n=== Who Am I ===\n")
    print(f"  Email: {email}")
    print(f"  Student courses: {len(student_courses)}")
    print(f"  Instructor courses: {len(instructor_courses)}")
    if student_courses:
        latest = sorted(
            student_courses.items(),
            key=lambda item: (item[1].get("year", ""), item[1].get("semester", ""), item[1].get("name", "")),
            reverse=True,
        )[:3]
        print("  Recent student courses:")
        for course_id, course in latest:
            print(f"    {course_id}: {course.get('name', 'Unknown')}")
    return 0


def get_autograder_results(
    connection: GSConnection,
    course_id: str,
    assignment_id: str,
    submission_id: str | None = None,
) -> dict[str, Any]:
    """Fetch autograder results for a submission (latest if omitted)."""
    target_sub_id = submission_id or get_latest_submission_id(
        connection.session, course_id, assignment_id
    )
    return get_submission_json(
        connection.session, course_id, assignment_id, target_sub_id
    )



def poll_autograder_status(
    session,
    course_id: str,
    assignment_id: str,
    submission_id: str,
    interval: int = 10,
    timeout: int = 600,
) -> dict[str, Any]:
    """Poll Gradescope until the autograder finishes running.

    Returns assignment_submission status metadata when status is 'processed'.
    Raises TimeoutError if the autograder does not finish within timeout.
    """
    elapsed = 0

    while True:
        data = get_submission_json(
            session,
            course_id,
            assignment_id,
            submission_id,
            only_keys=["assignment_submission"],
        )
        sub_data = data.get("assignment_submission") or {}
        status = sub_data.get("status", "unknown")

        if status == "processed":
            return sub_data

        if elapsed >= timeout:
            raise TimeoutError(
                f"Autograder did not finish after {timeout}s (last status: {status})"
            )

        mins, secs = divmod(elapsed, 60)
        elapsed_str = f"{mins}m{secs:02d}s" if mins else f"{secs}s"
        print(
            f"  Waiting for autograder... ({status}, elapsed: {elapsed_str})",
            end="\r",
        )

        time.sleep(interval)
        elapsed += interval



def cmd_wait_for_results(args: argparse.Namespace) -> int:
    try:
        _, connection = login_connection(args.email, args.password)
        sub_id = get_latest_submission_id(
            connection.session, args.course_id, args.assignment_id
        )
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    try:
        status_data = get_submission_json(
            connection.session,
            args.course_id,
            args.assignment_id,
            sub_id,
            only_keys=["assignment_submission"],
        )
    except Exception as exc:
        print(f"Failed to check submission status: {exc}", file=sys.stderr)
        return 1

    current_status = (status_data.get("assignment_submission") or {}).get(
        "status", "unknown"
    )

    if current_status == "processed":
        print("Autograder already finished.")
    elif current_status in ("autograder_harness_started", "autograder_running"):
        print(f"Autograder is running (status: {current_status}). Waiting...\n")
        try:
            poll_autograder_status(
                connection.session,
                args.course_id,
                args.assignment_id,
                sub_id,
                interval=args.interval,
                timeout=args.timeout,
            )
        except TimeoutError as exc:
            print(f"\n{exc}", file=sys.stderr)
            print(
                "You can check results later with: gscli.py view-results -c {} -a {}".format(
                    args.course_id, args.assignment_id
                )
            )
            return 1
    else:
        print(f"Submission status: {current_status}")
        if current_status not in ("processed",):
            print("Autograder may not be configured for this assignment.")

    print(" " * 80, end="\r")

    try:
        data = get_autograder_results(
            connection,
            args.course_id,
            args.assignment_id,
            submission_id=sub_id,
        )
    except Exception as exc:
        print(f"Failed to fetch final results: {exc}", file=sys.stderr)
        return 1

    return render_autograder_results(
        data,
        course_id=args.course_id,
        assignment_id=args.assignment_id,
        failed_only=args.failed_only,
        show_stdout=args.show_stdout,
    )




def cmd_view_results(args: argparse.Namespace) -> int:
    try:
        _, connection = login_connection(args.email, args.password)
        data = get_autograder_results(connection, args.course_id, args.assignment_id)
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1

    return render_autograder_results(
        data,
        course_id=args.course_id,
        assignment_id=args.assignment_id,
        failed_only=args.failed_only,
        show_stdout=args.show_stdout,
    )




def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gradescope CLI tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    courses = sub.add_parser("list-courses", help="List all courses")
    courses.add_argument("--email", help="Email (default: from auth.txt or prompt)")
    courses.add_argument("--password", help="Password (default: from auth.txt or prompt)")
    courses.set_defaults(func=cmd_courses)

    assignments = sub.add_parser("list-assignments", help="List assignments for a course")
    assignments.add_argument("-c", "--course", dest="course_id", required=True, help="Course ID")
    assignments.add_argument("--email", help="Email (default: from auth.txt or prompt)")
    assignments.add_argument("--password", help="Password (default: from auth.txt or prompt)")
    assignments.add_argument("--open-only", action="store_true", help="Show only open assignments")
    assignments.set_defaults(func=cmd_assignments)

    submit = sub.add_parser("submit-assignment", help="Upload one or more files to an assignment")
    submit.add_argument("-c", "--course", dest="course_id", required=True, help="Course ID")
    submit.add_argument("-a", "--assignment", dest="assignment_id", required=True, help="Assignment ID")
    submit.add_argument("files", nargs="+", help="Files to upload")
    submit.add_argument("--leaderboard-name", help="Optional leaderboard name")
    submit.add_argument("--dry-run", action="store_true", help="Validate arguments without uploading")
    submit.add_argument("--wait", action="store_true", help="Wait for autograder to finish and show results")
    submit.add_argument("--interval", type=int, default=10, help="Poll interval in seconds (default: 10)")
    submit.add_argument("--timeout", type=int, default=600, help="Max wait time in seconds (default: 600)")
    submit.add_argument("--failed-only", action="store_true", help="Show only failed/errored tests (with --wait)")
    submit.add_argument("--show-stdout", action="store_true", help="Show full autograder stdout (with --wait)")
    submit.add_argument("--email", help="Email (default: from auth.txt or prompt)")
    submit.add_argument("--password", help="Password (default: from auth.txt or prompt)")
    submit.set_defaults(func=cmd_submit_assignment)

    deadlines = sub.add_parser("deadlines", help="Show upcoming assignment deadlines")
    deadlines.add_argument(
        "-c",
        "--course",
        dest="course_id",
        action="append",
        help="Restrict to one or more course IDs",
    )
    deadlines.add_argument("--include-closed", action="store_true", help="Include closed assignments")
    deadlines.add_argument("--limit", type=int, help="Maximum number of assignments to show")
    deadlines.add_argument("--email", help="Email (default: from auth.txt or prompt)")
    deadlines.add_argument("--password", help="Password (default: from auth.txt or prompt)")
    deadlines.set_defaults(func=cmd_deadlines)

    whoami = sub.add_parser("whoami", help="Show the logged-in account summary")
    whoami.add_argument("--email", help="Email (default: from auth.txt or prompt)")
    whoami.add_argument("--password", help="Password (default: from auth.txt or prompt)")
    whoami.set_defaults(func=cmd_whoami)

    results = sub.add_parser("view-results", help="View autograder results for an assignment")
    results.add_argument("-c", "--course", dest="course_id", required=True, help="Course ID")
    results.add_argument("-a", "--assignment", dest="assignment_id", required=True, help="Assignment ID")
    results.add_argument("--failed-only", action="store_true", help="Show only failed/errored tests")
    results.add_argument("--show-stdout", action="store_true", help="Show full autograder stdout")
    results.add_argument("--email", help="Email (default: from auth.txt or prompt)")
    results.add_argument("--password", help="Password (default: from auth.txt or prompt)")
    results.set_defaults(func=cmd_view_results)


    wait = sub.add_parser("wait-for-results", help="Wait for autograder to finish, then show results")
    wait.add_argument("-c", "--course", dest="course_id", required=True, help="Course ID")
    wait.add_argument("-a", "--assignment", dest="assignment_id", required=True, help="Assignment ID")
    wait.add_argument("--interval", type=int, default=10, help="Poll interval in seconds (default: 10)")
    wait.add_argument("--timeout", type=int, default=600, help="Max wait time in seconds (default: 600)")
    wait.add_argument("--failed-only", action="store_true", help="Show only failed/errored tests")
    wait.add_argument("--show-stdout", action="store_true", help="Show full autograder stdout")
    wait.add_argument("--email", help="Email (default: from auth.txt or prompt)")
    wait.add_argument("--password", help="Password (default: from auth.txt or prompt)")
    wait.set_defaults(func=cmd_wait_for_results)


    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
