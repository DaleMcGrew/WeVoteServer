from enum import Enum
import copy

_HEADER_PREFIX = "X-"
_COOKIE_PREFIX = "__Secure-"

class TokenHeaders(Enum):
    AUTHORIZATION = "Authorization"
    TOKEN_TYPE = _HEADER_PREFIX + "Token-Type"
    CREATE_TOKEN = _HEADER_PREFIX + "X-Create-Token"

    TOKEN_EXPIRATION = _HEADER_PREFIX + "Token-Expiration"
    TOKEN_MESSAGE = _HEADER_PREFIX + "Token-Message"

    USER_ID = _HEADER_PREFIX + "User-Id"
    TOKEN_ID = _HEADER_PREFIX + "Token-Id"
    TOKEN_KEY = _HEADER_PREFIX + "Token-Key"
    TOKEN_NEW_KEY = _HEADER_PREFIX + "Token-New-Key"
    TOKEN_STATUS = _HEADER_PREFIX + "Token-Status"

class TokenCookies(Enum):
    SYNC_DATA_WITH_MASTER_SERVERS_START_TOKEN_ID = _COOKIE_PREFIX + "Sync-Data-With-Master-Servers-Start-Token-Id"
    SYNC_DATA_WITH_MASTER_SERVERS_START_TOKEN_KEY = _COOKIE_PREFIX + "Sync-Data-With-Master-Servers-Start-Token-Key"

class TokenTypes(Enum):
    SINGLE_USE = "single_use"

class TokenResponse(Enum):
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