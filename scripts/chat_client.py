from getpass import getpass

import httpx


BASE_URL = "http://127.0.0.1:8000"


def main():

    customer_id = input(
        "Customer ID: "
    ).strip()

    password = getpass(
        "Password: "
    )

    with httpx.Client(
        timeout=180
    ) as client:

        login = client.post(
            f"{BASE_URL}/api/v1/auth/token",
            data={
                "username": customer_id,
                "password": password,
            },
        )

        if login.status_code != 200:

            print("Authentication failed")
            return

        token = login.json()["access_token"]

        headers = {
            "Authorization": f"Bearer {token}"
        }

        session_id = None

        print("\nDishCare AI is ready.")
        print("Type exit to leave.\n")

        while True:

            message = input(
                "You: "
            ).strip()

            if message.lower() == "exit":
                break

            if not message:
                continue

            payload = {
                "message": message
            }

            if session_id:

                payload["session_id"] = session_id

            try:

                response = client.post(
                    f"{BASE_URL}/api/v1/chat",
                    headers=headers,
                    json=payload,
                )

                response.raise_for_status()

                data = response.json()

                session_id = data["session_id"]

                print(
                    "\nDishCare AI:",
                    data["answer"],
                    "\n",
                )

                print(
                    "Intents:",
                    data["intents"],
                )

                if data["sources"]:

                    print(
                        "Sources:",
                        data["sources"],
                    )

                print()

            except httpx.HTTPStatusError as exc:

                print(
                    "API error:",
                    exc.response.status_code,
                    exc.response.text,
                )

            except httpx.RequestError:

                print(
                    "Connection error. Check the FastAPI server."
                )


if __name__ == "__main__":
    main()