import unittest
from utils import calculate_average, get_user_name


class TestCalculateAverage(unittest.TestCase):

    # --- Normal cases ---
    def test_integers(self):
        self.assertEqual(calculate_average([1, 2, 3, 4, 5]), 3.0)

    def test_floats(self):
        self.assertAlmostEqual(calculate_average([1.5, 2.5, 3.0]), 2.333333, places=5)

    def test_mixed_int_and_float(self):
        self.assertEqual(calculate_average([1, 2.5, 3.5]), 2.333333333333333)

    def test_single_element(self):
        self.assertEqual(calculate_average([42]), 42.0)

    def test_negative_numbers(self):
        self.assertEqual(calculate_average([-3, -1, -2]), -2.0)

    def test_mixed_positive_and_negative(self):
        self.assertEqual(calculate_average([-5, 5]), 0.0)

    def test_returns_float(self):
        result = calculate_average([2, 4])
        self.assertIsInstance(result, float)

    # --- Edge cases ---
    def test_empty_list_returns_zero(self):
        self.assertEqual(calculate_average([]), 0)

    def test_all_zeros(self):
        self.assertEqual(calculate_average([0, 0, 0]), 0.0)

    def test_large_numbers(self):
        self.assertEqual(calculate_average([1_000_000, 2_000_000]), 1_500_000.0)


class TestGetUserName(unittest.TestCase):

    # --- Normal cases ---
    def test_returns_uppercase_name(self):
        self.assertEqual(get_user_name({"name": "alice"}), "ALICE")

    def test_already_uppercase(self):
        self.assertEqual(get_user_name({"name": "BOB"}), "BOB")

    def test_mixed_case_name(self):
        self.assertEqual(get_user_name({"name": "Charlie"}), "CHARLIE")

    def test_name_with_spaces(self):
        self.assertEqual(get_user_name({"name": "john doe"}), "JOHN DOE")

    def test_extra_keys_ignored(self):
        self.assertEqual(get_user_name({"name": "dave", "age": 30}), "DAVE")

    # --- Edge cases ---
    def test_missing_name_key_returns_empty_string(self):
        self.assertEqual(get_user_name({"age": 25}), "")

    def test_name_is_none_returns_empty_string(self):
        self.assertEqual(get_user_name({"name": None}), "")

    def test_name_is_empty_string_returns_empty_string(self):
        self.assertEqual(get_user_name({"name": ""}), "")

    def test_empty_dict_returns_empty_string(self):
        self.assertEqual(get_user_name({}), "")

    # --- Wrong-type inputs ---
    def test_input_is_none_returns_empty_string(self):
        self.assertEqual(get_user_name(None), "")

    def test_input_is_string_returns_empty_string(self):
        self.assertEqual(get_user_name("alice"), "")

    def test_input_is_list_returns_empty_string(self):
        self.assertEqual(get_user_name(["alice"]), "")

    def test_input_is_integer_returns_empty_string(self):
        self.assertEqual(get_user_name(42), "")


if __name__ == "__main__":
    unittest.main()
