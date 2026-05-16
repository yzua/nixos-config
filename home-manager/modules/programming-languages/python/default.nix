# Python development environment (uv, ruff, poetry, pytest, etc).

{
  config,
  lib,
  pkgs,
  ...
}:

let
  mkShellAliasPrograms = import ../../../_helpers/_shell-alias-programs.nix;
in
{
  programs =
    let
      pipAliases = {
        pipi = "pip install";
        pipu = "pip install --upgrade";
        pipr = "pip uninstall";
        pipl = "pip list";
        pipf = "pip freeze";
        pipreq = "pip install -r requirements.txt";
        pipfreeze = "pip freeze > requirements.txt";
      };

      uvPipAliases = {
        uvi = "uv pip install";
        uvu = "uv pip install --upgrade";
        uvr = "uv pip uninstall";
        uvl = "uv pip list";
        uvf = "uv pip freeze";
        uvreq = "uv pip install -r requirements.txt";
        uvfreeze = "uv pip freeze > requirements.txt";
      };

      shellAliases = {
        py = "python3";
        pyi = "python3 -i";
        pym = "python3 -m";
        uvinit = "uv init";
        uvadd = "uv add";
        uvdev = "uv add --dev";
        uvrun = "uv run";
        uvsync = "uv sync";
        venvc = "python3 -m venv venv";
        venva = "source venv/bin/activate";
        venvd = "deactivate";
        venvi = "venv/bin/pip install";
        rufff = "ruff format";
        ruffl = "ruff check";
        rufffi = "ruff format --check";
        mypyl = "mypy --ignore-missing-imports";
        pytestr = "pytest -v";
        pytestrw = "pytest -v --tb=short";
        coverage = "coverage run -m pytest && coverage report";
        jupyterl = "jupyter lab";
        jupytern = "jupyter notebook";
      }
      // pipAliases
      // uvPipAliases;
    in
    (mkShellAliasPrograms { inherit shellAliases; })
    // {
      git.ignores = import ./_gitignores.nix;
    };

  home = {
    # Project-specific deps should use dev-shells or uv
    packages = with pkgs; [
      python3
      python3Packages.pip
      python3Packages.virtualenv
      poetry
      uv
      ruff
      python3Packages.mypy
      python3Packages.pytest
      python3Packages.setuptools
      python3Packages.wheel
      python3Packages.ipython
      python3Packages.waybackpy # Wayback Machine API client for archived URL lookups
      python3Packages.z3-solver # SMT solver for constraint solving and crypto analysis
    ];

    sessionVariables = {
      PYTHONPATH = "${config.home.homeDirectory}/Projects/python";
      PYTHONSTARTUP = "${config.home.homeDirectory}/.pythonrc";
      PYTHONUTF8 = "1";
      VIRTUAL_ENV_DISABLE_PROMPT = "1";
      JUPYTER_CONFIG_DIR = "${config.home.homeDirectory}/.jupyter";
      JUPYTER_PLATFORM_DIRS = "1";
      POETRY_VIRTUALENVS_IN_PROJECT = "true";
      POETRY_NO_INTERACTION = "1";
      POETRY_PYPI_TOKEN_PYPI = "";
      PIP_DISABLE_PIP_VERSION_CHECK = "1";
      PIP_NO_WARN_SCRIPT_LOCATION = "1";
      PIP_INDEX_URL = "";
      UV_CACHE_DIR = "${config.xdg.cacheHome}/uv";
      UV_PYTHON_INSTALL_DIR = "${config.xdg.dataHome}/uv/python";
      UV_COMPILE_BYTECODE = "1";
      UV_LINK_MODE = "copy";
      PYTHONWARNINGS = "default";
    };

    sessionPath = [
      "${config.home.homeDirectory}/.local/bin"
      "${config.home.homeDirectory}/.poetry/bin"
    ];

    # Managed .pythonrc (replaces activation script for idempotent file management)
    file.".pythonrc".text = ''
      import atexit
      import os
      import readline
      import rlcompleter

      # Enable tab completion
      readline.parse_and_bind("tab: complete")

      # History file
      history_file = os.path.expanduser("~/.python_history")
      if os.path.exists(history_file):
        readline.read_history_file(history_file)
      atexit.register(readline.write_history_file, history_file)

      # Set history length
      readline.set_history_length(1000)

      # Enable colors in Python REPL
      os.environ['PYTHON_COLORS'] = '1'
    '';

    activation.createPythonWorkspace = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      $DRY_RUN_CMD mkdir -p $HOME/Projects/{python,django,flask,fastapi,data}
      $DRY_RUN_CMD mkdir -p $HOME/.jupyter
    '';
  };
}
