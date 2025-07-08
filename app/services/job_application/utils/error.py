""" Module to represent custome exceptions """

class AutofillException(Exception):
    """Exception raised when autofilling fails."""
    def __init__(self, error_type, message):
        # Initialize the base class (Exception)
        super().__init__(message)
        
        # Store the error type (e.g., Listbox, Input, etc.)
        self.error_type = error_type

    def __str__(self):
        # Customize the error message format to include the error type
        return f"{self.error_type} Error: {self.args[0]}"

class ApplyException(Exception):
    """Exception raised when applying fails."""