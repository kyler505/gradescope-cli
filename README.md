# Gradescope API CLI

A command-line interface for interacting with Gradescope's API, built on the `gradescopeapi` PyPI package. This tool allows you to submit assignments, view autograder results, and poll for autograder completion programmatically.

## Features

- Submit assignments to Gradescope courses
- View autograder results and scores
- Poll for autograder completion
- List courses and assignments
- View upcoming deadlines

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/kyler505/gradescope-cli.git
   cd gradescope-cli
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Set up a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

## Usage

### Authentication

Create an `auth.txt` file in the repository root with two lines:
1. Your Gradescope account email
2. Your Gradescope password

**Note:** `auth.txt` is ignored by Git (.gitignore) to protect your credentials.

### Commands

| Command | Description |
|---------|-------------|
| `whoami` | Logged-in account summary |
| `list-courses` | All courses (student + instructor) |
| `list-assignments -c <id>` | Assignments for a course (`--open-only`) |
| `submit-assignment -c <id> -a <id> <files>` | Upload files (`--wait`, `--dry-run`, `--leaderboard-name`) |
| `view-results -c <id> -a <id>` | View autograder results (`--failed-only`, `--show-stdout`) |
| `wait-for-results -c <id> -a <id>` | Poll until autograder finishes, then show results (`--interval`, `--timeout`) |
| `deadlines` | Upcoming assignment deadlines across courses |

### Examples

List all your courses:
```bash
python gscli.py list-courses
```

List open assignments for a course (ID: 1200912):
```bash
python gscli.py list-assignments -c 1200912 --open-only
```

Submit files to an assignment:
```bash
python gscli.py submit-assignment -c 1200912 -a 123456 file1.csv file2.csv
```

Wait for autograder results after submitting:
```bash
python gscli.py submit-assignment -c 1200912 -a 123456 file.csv --wait
```

## Known Course IDs

| Course | ID |
|--------|----|
| CSCE 421 500 - Machine Learning | 1200912 |
| CSCE 310 | 1232876 |

## Development

This CLI was originally developed for the CSCE 421 final project at Texas A&M University. It has since been generalized for programmatic Gradescope interaction.

### API Endpoints

Through exploration, these useful endpoints were discovered:

#### Submission JSON (full data)
```
GET /courses/{course_id}/assignments/{assignment_id}/submissions/{submission_id}.json?content=react
```

#### Lightweight polling (status only)
```
GET /courses/{course_id}/assignments/{assignment_id}/submissions/{submission_id}.json?content=react&only_keys[]=assignment_submission
```
Returns minimal JSON with just `assignment_submission.status` — cheap for repeated polling.

#### Available `only_keys[]` values
- `assignment_submission` — status, created_at, score
- `past_submissions` — list of past submissions
- `text_files` — submitted file AWS links
- `file_comments` — comments on submissions

### Autograder Results Structure

The `autograder_results` key in the full JSON response:
```json
{
  "score": 90.0,
  "tests": [
    {
      "name": "test_name",
      "score": 5.0,
      "number": "1.1",
      "output": "failure message",
      "status": "passed|failed|error",
      "max_score": 5.0
    }
  ],
  "output": "This is your 2nd submission.",
  "stdout": "autograder stdout...",
  "stdout_shown_to_students": true,
  "error_code": ""
}
```

### Submission Status Values

| Status | Meaning |
|--------|---------|
| `autograder_harness_started` | Autograder is running |
| `processed` | Autograder finished, results available |

## Tips

- **Leaderboard Name**: Some Gradescope forms require a leaderboard name on submission. If uploads fail or redirect back to the course page, retry with `--leaderboard-name <value>`. For the CSCE 421 final project, `erix` was the working value.
- **Verify CSVs**: Before resubmitting, verify the root CSVs (`test01-pred.csv`, `test02-pred.csv`, `test03-pred.csv`) still match the intended canonical outputs in `outputs/`; stale roots can silently point at the wrong model.
- **Lightweight Polling**: Use the lightweight polling endpoint (`only_keys[]=assignment_submission`) for frequent status checks, then fetch full results only when status becomes `processed`.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Original development for CSCE 421 Machine Learning at Texas A&M
- Built on the `gradescopeapi` PyPI package
