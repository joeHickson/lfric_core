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
The import is performed once per worker process at pool initialisation.
"""

import argparse
import os
import sys
import time

# Module-level reference populated by worker initializer
_psyclone_main = None


def _worker_init():
    """Initializer for each worker process — imports PSyclone once."""
    global _psyclone_main
    import logging
    import warnings
    logging.getLogger('psyclone').setLevel(logging.WARNING)
    warnings.filterwarnings('ignore', module='psyclone')
    from psyclone.generator import main as psyclone_main
    _psyclone_main = psyclone_main


def _resolve_opt_script(optimisation_path, dsl, stem):
    """Return (opt_script, label) for a given file stem."""
    if optimisation_path:
        local_script = os.path.join(optimisation_path, dsl, f"{stem}.py")
        global_script = os.path.join(optimisation_path, dsl, "global.py")
        if os.path.isfile(local_script):
            return local_script, "PSyclone - local optimisation"
        elif os.path.isfile(global_script):
            return global_script, "PSyclone - global optimisation"
    return None, "PSyclone"


def _process_one(args_tuple):
    """Process a single x90 file. Runs in a worker process."""
    x90_file, working_dir, config, optimisation_path, dsl, extras = args_tuple

    import io

    stem = os.path.relpath(x90_file, working_dir)
    stem = os.path.splitext(stem)[0]

    opt_script, label = _resolve_opt_script(optimisation_path, dsl, stem)

    psyclone_args = [
        '-api', 'lfric',
        '-d', working_dir,
        '--config', config,
        '-okern', os.path.join(working_dir, 'kernel'),
        '-oalg', os.path.join(working_dir, f'{stem}.f90'),
        '-opsy', os.path.join(working_dir, f'{stem}_psy.f90'),
    ]
    if opt_script:
        psyclone_args.extend(['-s', opt_script])
    psyclone_args.extend(extras)
    psyclone_args.append(x90_file)

    timestamp = time.strftime('%H:%M:%S')
    try:
        saved_stdout = sys.stdout
        saved_stderr = sys.stderr
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        try:
            _psyclone_main(psyclone_args)
        finally:
            sys.stdout = saved_stdout
            sys.stderr = saved_stderr
        return (0, f"{timestamp} *{label}* {stem}")
    except SystemExit as err:
        rc = err.code if err.code and err.code != 0 else 0
        return (rc, f"{timestamp} *{label}* {stem}")
    except Exception as err:
        return (1, f"{timestamp} *{label}* {stem} ERROR: {err}")


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
    parser.add_argument('-j', '--jobs', type=int, default=None,
                        help="Number of parallel workers (default: MAKE_THREADS or cpu_count)")
    args, extras = parser.parse_known_args()

    if not args.files:
        return

    n_workers = args.jobs or int(os.environ.get('MAKE_THREADS', '0') or '0') or os.cpu_count() or 1

    from concurrent.futures import ProcessPoolExecutor

    # Sort files by size descending for better load balancing —
    # large files are dispatched first so workers stay busy at the tail end
    sorted_files = sorted(args.files, key=lambda f: os.path.getsize(f), reverse=True)

    # Build task arguments
    tasks = [
        (x90, args.working_dir, args.config, args.optimisation_path, args.dsl, extras)
        for x90 in sorted_files
    ]

    # Use chunksize to reduce scheduling overhead for large file lists
    chunksize = max(1, len(tasks) // (n_workers * 4))

    rc = 0
    with ProcessPoolExecutor(max_workers=n_workers, initializer=_worker_init) as pool:
        for code, msg in pool.map(_process_one, tasks, chunksize=chunksize):
            print(msg, flush=True)
            if code:
                rc = code

    sys.exit(rc)


if __name__ == '__main__':
    main()

