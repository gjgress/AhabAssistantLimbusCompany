{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
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
          spec = {
            app = [ ];
          };

          # Generate overlay
          overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
          pyprojectOverrides = pkgs.lib.composeExtensions (uv2nix_hammer_overrides.overrides pkgs) (
            # use uv2nix_hammer_overrides.overrides_debug
            #   to see which versions were matched to which overrides
            #  use uv2nix_hammer_overrides.overrides_strict / overrides_strict_debug
            #  to use only overrides exactly matching your python package versions

            _final: _prev: {
              # place additional overlays here.
              #a_pkg = prev.a_pkg.overrideAttrs (old: nativeBuildInputs = old.nativeBuildInputs ++ [pkgs.someBuildTool] ++ (final.resolveBuildSystems { setuptools = [];});
              pyside6-essentials = _prev.pyside6-essentials.overrideAttrs (old: {
                autoPatchelfIgnoreMissingDeps = (old.autoPatchelfIgnoreMissingDeps or [ ]) ++ [
                  "libQt6VirtualKeyboardQml.so.6"
                ];
              });
            }
          );

          # Construct package set
          pythonSet = # Use base package set from pyproject.nix builders
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

          editablePythonSet = pythonSet.overrideScope editableOverlay;

          virtualenv =
            (editablePythonSet.mkVirtualEnv "aalc-dev-env" workspace.deps.all).overrideAttrs
              (old: {
                venvIgnoreCollisions = [ "*" ];
              });
        in
        {
          devShells.default = pkgs.mkShell {
            packages = [
              virtualenv
              pkgs.uv
            ]
            ++ lib.optionals (pkgs.stdenv.isLinux) [
              pkgs.xdotool
              pkgs.grim
              pkgs.xorg.libX11
              pkgs.xorg.libXrandr
              pkgs.xorg.libXinerama
            ];

            nativeBuildInputs = lib.optionals (pkgs.stdenv.isLinux) [
              pkgs.linuxHeaders
            ];

            env = {
              UV_NO_SYNC = "1";
              UV_PYTHON = editablePythonSet.python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            }
            // lib.optionalAttrs (pkgs.stdenv.isLinux) {
              # Point evdev build to Linux headers
              C_INCLUDE_PATH = "${pkgs.linuxHeaders}/include";
              # X11 libraries for mss and python-xlib
              LD_LIBRARY_PATH = lib.makeLibraryPath [
                pkgs.xorg.libX11
                pkgs.xorg.libXrandr
                pkgs.xorg.libXinerama
              ];
            };

            shellHook = ''
              unset PYTHONPATH
              export REPO_ROOT=$(git rev-parse --show-toplevel)
            '';
          };

        };
    };
}
