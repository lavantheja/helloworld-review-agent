def calculate_average(numbers: list[int | float]) -> float:
    """Calculate the arithmetic mean of a list of numbers.

    Args:
        numbers (list): A list of numeric values to average.

    Returns:
        float: The average of the provided numbers, or 0 if the list is empty.
    """
    if not numbers:
        return 0
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)


def get_user_name(user: dict) -> str:
    """Retrieve and uppercase a user's name from a user dictionary.

    Args:
        user (dict): A dictionary expected to contain a "name" key with the user's name.

    Returns:
        str: The user's name in uppercase, or an empty string if the name is missing,
             falsy, or if the input is not a dictionary.
    """
    name = user.get("name") if isinstance(user, dict) else None
    if not name:
        return ""
    return name.upper()