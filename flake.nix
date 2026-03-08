{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix_hammer_overrides = {
      url = "github:TyberiusPrime/uv2nix_hammer_overrides";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pre-commit-hooks = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{
      self,
      nixpkgs,
      flake-parts,
      pyproject-nix,
      uv2nix,
      uv2nix_hammer_overrides,
      pyproject-build-systems,
      pre-commit-hooks,
      treefmt-nix,
    }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
        inputs.treefmt-nix.flakeModule
        inputs.pre-commit-hooks.flakeModule
      ];

      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
        "x86_64-darwin"
      ];

      perSystem =
        {
          config,
          pkgs,
          lib,
          system,
          ...
        }:
        let
          # Load a uv workspace from a workspace root.
          # Uv2nix treats all uv projects as workspace projects.
          workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

          python = pkgs.python313;

          hacks = pkgs.callPackage pyproject-nix.build.hacks {};

          # Generate overlay
          overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
          pyprojectOverrides = pkgs.lib.composeExtensions (uv2nix_hammer_overrides.overrides pkgs) (
            # use uv2nix_hammer_overrides.overrides_debug
            #   to see which versions were matched to which overrides
            #  use uv2nix_hammer_overrides.overrides_strict / overrides_strict_debug
            #  to use only overrides exactly matching your python package versions

            _final: _prev:
            let
              qt6_full = with pkgs.qt6; [
                qtbase

                # optional
                qt3d
                qtcharts
                qtconnectivity
                qtdatavis3d
                qtdeclarative
                qthttpserver
                qtmultimedia
                qtnetworkauth
                qtquick3d
                qtremoteobjects
                qtscxml
                qtsensors
                qtspeech
                qtsvg
                qtwebchannel
                qtwebsockets
                qtwebview
                qtpositioning
                qtlocation
                qtshadertools
                qtserialport
                qtserialbus
                qtgraphs
                qttools
                qtvirtualkeyboard

                qtwayland
                qtwebengine
                qt3d
                qtscxml
              ];
              qt_linked = pkgs.symlinkJoin {
                name = "qt_linked";
                paths = qt6_full;
              };
            in
            {
              # place additional overlays here.
              pyside6-addons = _prev.pyside6-addons.overrideAttrs (old: {
                dontWrapQtApps = true;
                buildInputs = [
                  qt_linked
                  pkgs.speechd
                  pkgs.pcsclite
                ];
                # Somehow `autopatchelf` does not find the `shiboken6` and `pyside-essentials` libraries.
                preFixup = ''
                  addAutoPatchelfSearchPath ${_final.shiboken6}/${_final.python.sitePackages}/shiboken6
                  addAutoPatchelfSearchPath ${_final.pyside6-essentials}/${_final.python.sitePackages}/PySide6
                '';
              });
              pyside6-essentials = _prev.pyside6-essentials.overrideAttrs (old: {
                dontWrapQtApps = true;
                autoPatchelfIgnoreMissingDeps = (old.autoPatchelfIgnoreMissingDeps or [ ]) ++ [
                  "libmysqlclient.so.21"
                  "libmimerapi.so"
                  "libQt6VirtualKeyboardQml.so.6"
                ];
                buildInputs = [
                  qt_linked
                  pkgs.gtk3
                  pkgs.libxkbcommon
                  pkgs.postgresql.lib

                  pkgs.unixODBC
                ];
                # Somehow `autopatchelf` does not find the `shiboken6` library.
                preFixup = ''
                  addAutoPatchelfSearchPath ${_final.shiboken6}/${_final.python.sitePackages}/shiboken6
                '';
              });
              evdev = _prev.evdev.overrideAttrs (old: {
                patchPhase = ''
                  substituteInPlace setup.py \
                    --replace-fail /usr/include ${pkgs.linuxHeaders}/include
                '';
                buildInputs = [ pkgs.linuxHeaders ];
              });
              tkinter = hacks.nixpkgsPrebuilt {
                from = python.pkgs.tkinter;
              };
            }
          );

          # Construct package set
          pythonSet' = # Use base package set from pyproject.nix builders
            (pkgs.callPackage pyproject-nix.build.packages {
              inherit python;
            }).overrideScope
              (
                lib.composeManyExtensions [
                  pyproject-build-systems.overlays.default
                  overlay
                  pyprojectOverrides
                ]
              );

          editableOverlay = workspace.mkEditablePyprojectOverlay {
            # Use environment variable pointing to editable root directory
            root = "$REPO_ROOT";
            # Optional: Only enable editable for these packages
            # members = [ "hello-world" ];
          };

          editablePythonSet = pythonSet'.overrideScope editableOverlay;

          virtualenv =
            (editablePythonSet.mkVirtualEnv "aalc-dev-env" (workspace.deps.all // {
              tkinter = [ ];
            })).overrideAttrs
              (old: {
                venvIgnoreCollisions = [ "*" ];
              });

          pythonSet = pythonSet'.pythonPkgsHostHost.overrideScope pyprojectOverrides;
        in
        {
          devShells.default = pkgs.mkShell {
            nativeBuildInputs = [ pkgs.uv ];
            buildInputs = [
              virtualenv
            ]
            ++ lib.optionals (pkgs.stdenv.isLinux) [
              pkgs.xdotool
              pkgs.xorg.libX11
              pkgs.xorg.libXrandr
              pkgs.xorg.libXinerama
            ];

            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = editablePythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            };

            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
            '';
          };

          packages.default = (pythonSet.mkVirtualEnv "example-venv" (workspace.deps.default // {
            tkinter = [ ];
            ahab-assistant-limbus-company = [ ];
          })).overrideAttrs (old: {
            venvIgnoreCollisions = [ "*" ];
          });
        };
    };
}
