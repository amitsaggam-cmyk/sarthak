import json
from pathlib import Path

from app.services.verification import verify_email


def load_dummy_email() -> dict:
    """Load one dummy verification email from a local JSON fixture."""

    fixture_path = Path(__file__).parent / "app" / "data" / "dummy_verification_email.json"
    with fixture_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def run_dummy_test() -> None:
    """Run the HR verification pipeline against the dummy email fixture."""

    email = load_dummy_email()
    result = verify_email(email)

    print("Dummy verification test")
    print("=======================")
    print(f"Email ID: {result.email_id}")
    print(f"Sender: {result.sender}")
    print(f"Subject: {result.subject}")
    print(f"All fields match: {result.all_fields_match}")
    print()
    print("Field results:")
    for field_result in result.field_results:
        status = "PASS" if field_result.matches else "FAIL"
        print(
            f"- {field_result.field}: {status} "
            f"(claimed={field_result.claimed_value}, workday={field_result.workday_value})"
        )
    print()
    print("Safe reply preview:")
    print(result.recommended_reply)


if __name__ == "__main__":
    run_dummy_test()
