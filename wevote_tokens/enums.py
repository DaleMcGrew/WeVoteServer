from enum import Enum
import copy

class Prefixes(Enum):
    HEADER_PREFIX = "X-"
    COOKIE_PREFIX = "__Secure-"

class TokenHeaders(Enum):
    AUTHORIZATION = "Authorization"
    TOKEN_TYPE = Prefixes.HEADER_PREFIX.value + "Token-Type"
    CREATE_TOKEN = Prefixes.HEADER_PREFIX.value + "Create-Token"

    TOKEN_EXPIRATION = Prefixes.HEADER_PREFIX.value + "Token-Expiration"
    TOKEN_MESSAGE = Prefixes.HEADER_PREFIX.value + "Token-Message"
    TOKEN_CREATION = Prefixes.HEADER_PREFIX.value + "Token-Creation"
    TOKEN_AUTHENTICATION = Prefixes.HEADER_PREFIX.value + "Token-Authentication"

    USER_ID = Prefixes.HEADER_PREFIX.value + "User-Id"
    TOKEN_KEY = Prefixes.HEADER_PREFIX.value + "Token-Key"
    TOKEN_NEW_KEY = Prefixes.HEADER_PREFIX.value + "Token-New-Key"
    TOKEN_STATUS = Prefixes.HEADER_PREFIX.value + "Token-Status"

class TokenCookies(Enum):
    SYNC_DATA_WITH_MASTER_SERVERS_START_TOKEN_ID = Prefixes.COOKIE_PREFIX.value + "Sync-Data-With-Master-Servers-Start-Token-Id"
    SYNC_DATA_WITH_MASTER_SERVERS_START_TOKEN_KEY = Prefixes.COOKIE_PREFIX.value + "Sync-Data-With-Master-Servers-Start-Token-Key"
    SYNC_DATA_WITH_MASTER_SERVERS_START_USER_ID = Prefixes.COOKIE_PREFIX.value + "Sync-Data-With-Master-Servers-Start-Wevote-Id"

class TokenTypes(Enum):
    SINGLE_USE = "single_use"

class TokenResponseStatus(Enum):
    AUTHENTICATION_PROCESSING_ERROR = "AUTHENTICATION_PROCESSING_ERROR"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_AUTHENTICATION_ARGUMENTS = "INVALID_AUTHENTICATION_ARGUMENTS"
    INVALID_TOKEN_TYPE = "INVALID_TOKEN_TYPE"

class TokenResponse(Enum):
    # MAKE SURE TO UPDATE THIS WHEN ADDING NEW HEADERS OR KEYS
    HEADERS_MAPPING = {
        'token_creation': TokenHeaders.TOKEN_CREATION.value,
        'token_authentication': TokenHeaders.TOKEN_AUTHENTICATION.value,
    }

    TOKEN_RESPONSE = {
        'token_creation': None,
        'token_authentication': None,
    }

    TOKEN_CREATION = {
        'success': False,
        'status': None,
        'error_message': None,
        'token_info': None
    }

    TOKEN_AUTHENTICATION = {
        'success': False,
        'status': None,
        'error_message': None,
        'token_info': None
    }

    def get_value(self):
        return copy.deepcopy(self._value_)

class TokenInfo(Enum):
    TOKEN_CREATION = {
        'success': False,
        'status': None,
        'token_pk': None,
        'expiration_datetime': None,
        'user_id': None,
    }

    TOKEN_AUTHENTICATION = {
        'success': False,
        'status': None,
        'scope': None,
        'scope_display': None,
        'expiration_datetime': None,
        'json_data': None,
        'user_id': None,
        'expired': False,
    }

    def get_value(self):
        return copy.deepcopy(self._value_)
