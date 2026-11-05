"""Explicit simulation runtime assembly; B/C prototype migration adapter."""
import importlib.util
import os
from pathlib import Path
import sys

from edge.config import ConfigurationError


def simulation_app(settings):
    if settings.device_id != 'demo01':
        raise ConfigurationError('simulation requires AQUAGUARD_DEVICE_ID=demo01')
    token=os.environ.get('AQUAGUARD_C_TOKEN','')
    try:
        key=bytes.fromhex(os.environ.get('AQUAGUARD_C_CURSOR_KEY',''))
    except ValueError:
        raise ConfigurationError('AQUAGUARD_C_CURSOR_KEY must be hex') from None
    if len(token)<24 or len(key)<32:
        raise ConfigurationError('simulation requires token >=24 chars and cursor key >=32 bytes')
    raw=os.environ.get('AQUAGUARD_DB','').strip()
    if not raw:
        raise ConfigurationError('simulation requires explicit AQUAGUARD_DB')
    path=Path(raw).resolve()
    root=Path(__file__).resolve().parents[1]
    prototype=root/'spikes/C-business'
    if str(prototype) not in sys.path:
        sys.path.insert(0,str(prototype))
    spec=importlib.util.spec_from_file_location('aquaguard_c_runtime',prototype/'run.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        module.WaterService(path)
    app=module.build(path,token=token,cursor_key=key,simulate=True)
    app.state.settings=settings
    return app
