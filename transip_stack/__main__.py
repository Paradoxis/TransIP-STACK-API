import os
from argparse import ArgumentParser
from multiprocessing.pool import ThreadPool
from threading import BoundedSemaphore

from transip_stack.stack import Stack
from transip_stack.utils import CustomHelpFormatter, directories, files


lock = BoundedSemaphore()


def main():
    """
    Main entry point of the application
    :return: None
    """
    args = ArgumentParser(
        usage='stack <action> <file or directory> [arguments]',
        formatter_class=CustomHelpFormatter,
        description=(
            'TransIP Stack command line interface. Credentials '
            'are set using the STACK_USERNAME, STACK_PASSWORD '
            'and STACK_HOSTNAME environment variables. To change '
            'the upload directory, set the STACK_DIRECTORY environment '
            'variable.'))

    args.add_argument('action', action='store', help=(
        'Action to perform, currently only accepts uploads.'))

    args.add_argument('file_or_directory', action='store', nargs='?', default='.', help=(
        'File or directory to upload, download or inspect. Defaults to the '
        'current working directory.'))

    args.add_argument('-t', '--threads', type=int, default=8)

    args = args.parse_args()

    with Stack(
        username=os.getenv('STACK_USERNAME'),
        password=os.getenv('STACK_PASSWORD'),
        hostname=os.getenv('STACK_HOSTNAME')
    ) as stack:

        stack.cd(os.getenv('STACK_DIRECTORY'))

        if args.action.lower() in ('u', 'upload'):
            return upload(stack, args)

        # TODO: Download functionality
        # if args.action.lower() in ('d', 'download'):
        #     return download(stack, args)


def log(message, *, prefix='*'):
    lock.acquire()
    print(f'[{prefix}] {message}')
    lock.release()


def upload(stack, args):
    def upload_file(file):
        try:
            stack.file(file)
            log(f'Skipping: {file!r} (already exists)')
        except StackException:
            stack.upload(file)
            log(f'Uploaded: {file!r}')

    if os.path.isfile(args.file_or_directory):
        return upload_file(args.file_or_directory)

    log('Setting up directory structure..', prefix='+')

    # Set up directory structure, can't be threaded as a
    # sub directory might be created before a parent directory is created.
    for directory in directories(args.file_or_directory):
        log(f'Creating directory: {directory!r}')
        stack.mkdir(directory)

    log('Starting upload..', prefix='+')

    pool = ThreadPool(processes=args.threads)
    pool.map_async(upload_file, files(args.file_or_directory))
    pool.close()
    pool.join()


if __name__ == '__main__':
    main()
