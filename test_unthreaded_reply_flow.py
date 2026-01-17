import unittest
from unittest.mock import patch, MagicMock
from email_integration.advanced_thread_handler import handle_unthreaded_reply

class TestUnthreadedReplyFlow(unittest.TestCase):

    @patch('email_integration.advanced_thread_handler.get_active_pos_by_email')
    @patch('email_integration.advanced_thread_handler.get_po_state')
    @patch('email_integration.advanced_thread_handler.process_inbound_email')
    def test_single_active_po(self, mock_process_inbound_email, mock_get_po_state, mock_get_active_pos_by_email):
        # Mocking the email data
        email_data = {
            'from': 'test@example.com',
            'subject': 'Re: Your Order',
            'body': 'I have a question about my order.'
        }

        # Mocking the active POs
        mock_get_active_pos_by_email.return_value = ['PO123']

        # Mocking the PO state
        mock_get_po_state.return_value = {
            'threads': [
                {'message_id': '<message1@example.com>'},
                {'message_id': '<message2@example.com>'}
            ]
        }

        # Call the function
        handle_unthreaded_reply(email_data)

        # Assert that process_inbound_email was called with the correct arguments
        mock_process_inbound_email.assert_called_once_with(
            from_sender='test@example.com',
            subject='Re: Your Order',
            body='I have a question about my order.',
            po_number_hint='PO123',
            message_id='<message2@example.com>',
            references='<message2@example.com>'
        )

    @patch('email_integration.advanced_thread_handler.get_active_pos_by_email')
    @patch('email_integration.advanced_thread_handler.get_conversation_histories')
    @patch('email_integration.advanced_thread_handler.find_best_matching_po')
    @patch('email_integration.advanced_thread_handler.get_po_state')
    @patch('email_integration.advanced_thread_handler.process_inbound_email')
    def test_multiple_active_pos(self, mock_process_inbound_email, mock_get_po_state, mock_find_best_matching_po, mock_get_conversation_histories, mock_get_active_pos_by_email):
        # Mocking the email data
        email_data = {
            'from': 'test@example.com',
            'subject': 'Re: Your Order',
            'body': 'I have a question about my order.'
        }

        # Mocking the active POs
        mock_get_active_pos_by_email.return_value = ['PO123', 'PO456']

        # Mocking the conversation histories
        mock_get_conversation_histories.return_value = {'PO123': 'History 1', 'PO456': 'History 2'}

        # Mocking the best matching PO
        mock_find_best_matching_po.return_value = 'PO456'

        # Mocking the PO state
        mock_get_po_state.return_value = {
            'threads': [
                {'message_id': '<message3@example.com>'},
                {'message_id': '<message4@example.com>'}
            ]
        }

        # Call the function
        handle_unthreaded_reply(email_data)

        # Assert that process_inbound_email was called with the correct arguments
        mock_process_inbound_email.assert_called_once_with(
            from_sender='test@example.com',
            subject='Re: Your Order',
            body='I have a question about my order.',
            po_number_hint='PO456',
            message_id='<message4@example.com>',
            references='<message4@example.com>'
        )

if __name__ == '__main__':
    unittest.main()
