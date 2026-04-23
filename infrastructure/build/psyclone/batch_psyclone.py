#!/usr/bin/env python
# -----------------------------------------------------------------------------
#  (C) Crown copyright 2026 Met Office. All rights reserved.
#  The file LICENCE, distributed with this code, contains details of the terms
#  under which the code may be used.
# -----------------------------------------------------------------------------
"""
Invoke psyclone on a batch of x90 files.

This script receives all x90 files at once from the build system and
invokes psyclone for each one, selecting the appropriate optimisation
script (per-file, global, or none) automatically.

PSyclone is loaded as a Python module and called directly to avoid
paying the cost of starting a new Python interpreter for every file.
"""

import argparse
import os
import sys

from psyclone.generator import main as psyclone_main


def main():
    parser = argparse.ArgumentParser(
        description="Batch-invoke psyclone on multiple x90 files.")
    parser.add_argument('-d', '--working-dir', required=True,
                        help="PSyclone working directory")
    parser.add_argument('--config', required=True,
                        help="Path to psyclone config file")
    parser.add_argument('--optimisation-path', default=None,
                        help="Root path for optimisation scripts")
    parser.add_argument('--dsl', default='psykal',
                        help="DSL subdirectory for optimisation scripts")
    parser.add_argument('--file', dest='files', action='append',
                        default=[],
                        help="x90 file to process (repeat for each file)")
    args, extras = parser.parse_known_args()

    if not args.files:
        return

    rc = 0
    for x90_file in args.files:
        # Derive the stem relative to the working directory
        stem = os.path.relpath(x90_file, args.working_dir)
        stem = os.path.splitext(stem)[0]

        # Determine which optimisation script (if any) to use
        opt_script = None
        if args.optimisation_path:
            local_script = os.path.join(
                args.optimisation_path, args.dsl, f"{stem}.py")
            global_script = os.path.join(
                args.optimisation_path, args.dsl, "global.py")
            if os.path.isfile(local_script):
                opt_script = local_script
                label = "PSyclone - local optimisation"
            elif os.path.isfile(global_script):
                opt_script = global_script
                label = "PSyclone - global optimisation"
            else:
                label = "PSyclone"
        else:
            label = "PSyclone"

        psyclone_args = [
            '-api', 'lfric',
            '-d', args.working_dir,
            '--config', args.config,
            '-okern', os.path.join(args.working_dir, 'kernel'),
            '-oalg', os.path.join(args.working_dir, f'{stem}.f90'),
            '-opsy', os.path.join(args.working_dir, f'{stem}_psy.f90'),
        ]
        if opt_script:
            psyclone_args.extend(['-s', opt_script])
        psyclone_args.extend(extras)
        psyclone_args.append(x90_file)

        print(f"{label}: {stem}")
        try:
            psyclone_main(psyclone_args)
        except SystemExit as err:
            if err.code and err.code != 0:
                rc = err.code
        except Exception as err:
            print(f"Error processing {stem}: {err}", file=sys.stderr)
            rc = 1

    sys.exit(rc)


if __name__ == '__main__':
    main()

