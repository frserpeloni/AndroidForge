import unittest

from installer_gui import close_block_message


class InstallerGuiPolicyTests(unittest.TestCase):
    def test_close_is_blocked_while_installation_is_active(self):
        self.assertEqual(
            close_block_message(True),
            "Aguarde o término da operação antes de fechar o assistente.",
        )

    def test_close_is_allowed_when_installation_is_idle(self):
        self.assertIsNone(close_block_message(False))


if __name__ == "__main__":
    unittest.main()
