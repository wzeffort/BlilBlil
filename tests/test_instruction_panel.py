import unittest

import core.utils as utils


class InstructionImageTests(unittest.TestCase):
    def test_wide_image_is_scaled_down_by_smallest_integer_factor(self):
        calculate = getattr(
            utils, "image_subsample_factor", lambda width, max_width: None
        )

        self.assertEqual(2, calculate(814, 520))

    def test_image_that_already_fits_keeps_original_size(self):
        calculate = getattr(
            utils, "image_subsample_factor", lambda width, max_width: None
        )

        self.assertEqual(1, calculate(371, 520))


if __name__ == "__main__":
    unittest.main()
