"""Canal local de parada da SERMAX Platform por evento Win32 com DACL restrita."""
from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes


ERROR_FILE_NOT_FOUND = 2
ERROR_ACCESS_DENIED = 5
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258
WAIT_FAILED = 0xFFFFFFFF
INFINITE = 0xFFFFFFFF
TOKEN_QUERY = 0x0008
TOKEN_USER_CLASS = 1


class StopEventError(RuntimeError):
    """Falha ao criar, abrir, sinalizar ou aguardar o evento de parada."""


class StopEventAlreadyExists(StopEventError):
    """O nome reservado está ocupado ou protegido por ACL incompatível; a propriedade é desconhecida."""


class StopEventNotFound(StopEventError):
    """Não existe evento de parada para a identidade e sessão atuais."""


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", wintypes.LPVOID), ("Attributes", wintypes.DWORD)]


class TOKEN_USER(ctypes.Structure):
    _fields_ = [("User", SID_AND_ATTRIBUTES)]


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", wintypes.DWORD),
        ("lpSecurityDescriptor", wintypes.LPVOID),
        ("bInheritHandle", wintypes.BOOL),
    ]


class _Win32:
    def __init__(self):
        if os.name != "nt":
            raise StopEventError("O controle de parada por evento está disponível somente no Windows.")
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        k32, adv = self.kernel32, self.advapi32

        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.CloseHandle.argtypes = [wintypes.HANDLE]
        k32.CloseHandle.restype = wintypes.BOOL
        k32.LocalFree.argtypes = [wintypes.HLOCAL]
        k32.LocalFree.restype = wintypes.HLOCAL
        k32.CreateEventW.argtypes = [
            ctypes.POINTER(SECURITY_ATTRIBUTES), wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR
        ]
        k32.CreateEventW.restype = wintypes.HANDLE
        k32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
        k32.OpenEventW.restype = wintypes.HANDLE
        k32.SetEvent.argtypes = [wintypes.HANDLE]
        k32.SetEvent.restype = wintypes.BOOL
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.WaitForSingleObject.restype = wintypes.DWORD

        adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        adv.OpenProcessToken.restype = wintypes.BOOL
        adv.GetTokenInformation.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD)
        ]
        adv.GetTokenInformation.restype = wintypes.BOOL
        adv.ConvertSidToStringSidW.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
        adv.ConvertSidToStringSidW.restype = wintypes.BOOL
        adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.DWORD)
        ]
        adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL

    @staticmethod
    def error(operation: str) -> StopEventError:
        code = ctypes.get_last_error()
        return StopEventError(f"{operation} falhou (Win32={code}).")


def _current_user_sid(api: _Win32) -> str:
    token = wintypes.HANDLE()
    if not api.advapi32.OpenProcessToken(
        api.kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)
    ):
        raise api.error("OpenProcessToken")
    try:
        required = wintypes.DWORD()
        ctypes.set_last_error(0)
        api.advapi32.GetTokenInformation(
            token, TOKEN_USER_CLASS, None, 0, ctypes.byref(required)
        )
        if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER or not required.value:
            raise api.error("GetTokenInformation(size)")
        buffer = ctypes.create_string_buffer(required.value)
        if not api.advapi32.GetTokenInformation(
            token, TOKEN_USER_CLASS, buffer, required.value, ctypes.byref(required)
        ):
            raise api.error("GetTokenInformation")
        user = ctypes.cast(buffer, ctypes.POINTER(TOKEN_USER)).contents
        sid_text = wintypes.LPWSTR()
        if not api.advapi32.ConvertSidToStringSidW(user.User.Sid, ctypes.byref(sid_text)):
            raise api.error("ConvertSidToStringSid")
        try:
            return sid_text.value
        finally:
            api.kernel32.LocalFree(ctypes.cast(sid_text, wintypes.HLOCAL))
    finally:
        api.kernel32.CloseHandle(token)


def _event_name(api: _Win32) -> str:
    sid = _current_user_sid(api)
    digest = hashlib.sha256(sid.encode("ascii")).hexdigest()[:32]
    return f"Local\\SERMAX.Platform.Stop.{digest}"


class WindowsStopEvent:
    """Handle proprietário do evento criado pelo launcher."""

    def __init__(self, api: _Win32, handle, name: str):
        self._api = api
        self._handle = handle
        self.name = name

    def wait(self, timeout_ms: int = INFINITE) -> bool:
        result = self._api.kernel32.WaitForSingleObject(self._handle, timeout_ms)
        if result == WAIT_OBJECT_0:
            return True
        if result == WAIT_TIMEOUT:
            return False
        if result == WAIT_FAILED:
            raise self._api.error("WaitForSingleObject")
        raise StopEventError(f"WaitForSingleObject retornou estado inesperado: {result}")

    def close(self) -> None:
        if self._handle:
            handle, self._handle = self._handle, None
            if not self._api.kernel32.CloseHandle(handle):
                raise self._api.error("CloseHandle(event)")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _event_security_sddl(sid: str) -> str:
    """Builds a protected DACL granting only the current SID stop and wait rights."""
    return f"D:P(A;;0x00100002;;;{sid})"


def create_stop_event() -> WindowsStopEvent:
    """Cria evento novo com DACL protegida e acesso concedido ao SID atual."""
    api = _Win32()
    sid = _current_user_sid(api)
    name = f"Local\\SERMAX.Platform.Stop.{hashlib.sha256(sid.encode('ascii')).hexdigest()[:32]}"
    # D:P protege a DACL contra herança. O SID recebe SYNCHRONIZE e
    # EVENT_MODIFY_STATE, necessários para esperar e sinalizar o evento.
    sddl = _event_security_sddl(sid)
    descriptor = wintypes.LPVOID()
    descriptor_size = wintypes.DWORD()
    if not api.advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, 1, ctypes.byref(descriptor), ctypes.byref(descriptor_size)
    ):
        raise api.error("ConvertStringSecurityDescriptorToSecurityDescriptor")
    handle = None
    try:
        attributes = SECURITY_ATTRIBUTES(
            ctypes.sizeof(SECURITY_ATTRIBUTES), descriptor, False
        )
        ctypes.set_last_error(0)
        handle = api.kernel32.CreateEventW(
            ctypes.byref(attributes), False, False, name
        )
        if not handle:
            error_code = ctypes.get_last_error()
            if error_code == ERROR_ACCESS_DENIED:
                raise StopEventAlreadyExists(
                    "O evento reservado já existe ou possui ACL incompatível. A Plataforma não assumirá sua propriedade."
                )
            raise StopEventError(f"CreateEvent falhou (Win32={error_code}).")
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            api.kernel32.CloseHandle(handle)
            handle = None
            raise StopEventAlreadyExists(
                "O evento reservado já existia. A Plataforma não assumirá sua propriedade."
            )
        return WindowsStopEvent(api, handle, name)
    finally:
        api.kernel32.LocalFree(ctypes.cast(descriptor, wintypes.HLOCAL))


def signal_stop_event() -> None:
    """Sinaliza somente o evento da identidade e sessão Windows atuais."""
    api = _Win32()
    name = _event_name(api)
    handle = api.kernel32.OpenEventW(EVENT_MODIFY_STATE, False, name)
    if not handle:
        code = ctypes.get_last_error()
        if code == ERROR_FILE_NOT_FOUND:
            raise StopEventNotFound("Nenhuma instância SERMAX controlável foi encontrada nesta sessão.")
        if code == ERROR_ACCESS_DENIED:
            raise StopEventError("Acesso negado ao evento de parada da SERMAX.")
        raise StopEventError(f"OpenEvent falhou (Win32={code}).")
    try:
        if not api.kernel32.SetEvent(handle):
            raise api.error("SetEvent")
    finally:
        if not api.kernel32.CloseHandle(handle):
            raise api.error("CloseHandle(client event)")
