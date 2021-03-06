#!/usr/bin/env python3

# 1. Take protoxform artifacts from Bazel cache and pretty-print with protoprint.py.
# 2. In the case where we are generating an Envoy internal shadow, it may be
#    necessary to combine the current active proto, subject to hand editing, with
#    shadow artifacts from the previous verion; this is done via
#    merge_active_shadow.py.
# 3. Diff or copy resulting artifacts to the source tree.

import argparse
from collections import defaultdict
import functools
import multiprocessing as mp
import os
import pathlib
import re
import shutil
import string
import subprocess
import sys
import tempfile

from api_proto_plugin import utils

from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

# api/bazel/external_protos_deps.bzl must have a .bzl suffix for Starlark
# import, so we are forced to this workaround.
_external_proto_deps_spec = spec_from_loader(
    'external_proto_deps',
    SourceFileLoader('external_proto_deps', 'api/bazel/external_proto_deps.bzl'))
external_proto_deps = module_from_spec(_external_proto_deps_spec)
_external_proto_deps_spec.loader.exec_module(external_proto_deps)

# These .proto import direct path prefixes are already handled by
# api_proto_package() as implicit dependencies.
API_BUILD_SYSTEM_IMPORT_PREFIXES = [
    'google/api/annotations.proto',
    'google/protobuf/',
    'google/rpc/status.proto',
    'validate/validate.proto',
]

BUILD_FILE_TEMPLATE = string.Template(
    """# DO NOT EDIT. This file is generated by tools/proto_sync.py.

load("@envoy_api//bazel:api_build_system.bzl", "api_proto_package")

licenses(["notice"])  # Apache 2

api_proto_package($fields)
""")

IMPORT_REGEX = re.compile('import "(.*)";')
SERVICE_REGEX = re.compile('service \w+ {')
PACKAGE_REGEX = re.compile('\npackage: "([^"]*)"')
PREVIOUS_MESSAGE_TYPE_REGEX = re.compile(r'previous_message_type\s+=\s+"([^"]*)";')


class ProtoSyncError(Exception):
  pass


class RequiresReformatError(ProtoSyncError):

  def __init__(self, message):
    super(RequiresReformatError, self).__init__(
        '%s; either run ./ci/do_ci.sh fix_format or ./tools/proto_format/proto_format.sh fix to reformat.\n'
        % message)


def GetDirectoryFromPackage(package):
  """Get directory path from package name or full qualified message name

  Args:
    package: the full qualified name of package or message.
  """
  return '/'.join(s for s in package.split('.') if s and s[0].islower())


def GetDestinationPath(src):
  """Obtain destination path from a proto file path by reading its package statement.

  Args:
    src: source path
  """
  src_path = pathlib.Path(src)
  contents = src_path.read_text(encoding='utf8')
  matches = re.findall(PACKAGE_REGEX, contents)
  if len(matches) != 1:
    raise RequiresReformatError("Expect {} has only one package declaration but has {}".format(
        src, len(matches)))
  return pathlib.Path(GetDirectoryFromPackage(
      matches[0])).joinpath(src_path.name.split('.')[0] + ".proto")


def GetAbsRelDestinationPath(dst_root, src):
  """Obtain absolute path from a proto file path combined with destination root.

  Creates the parent directory if necessary.

  Args:
    dst_root: destination root path.
    src: source path.
  """
  rel_dst_path = GetDestinationPath(src)
  dst = dst_root.joinpath(rel_dst_path)
  dst.parent.mkdir(0o755, parents=True, exist_ok=True)
  return dst, rel_dst_path


def ProtoPrint(src, dst):
  """Pretty-print FileDescriptorProto to a destination file.

  Args:
    src: source path for FileDescriptorProto.
    dst: destination path for formatted proto.
  """
  print('ProtoPrint %s' % dst)
  subprocess.check_output([
      'bazel-bin/tools/protoxform/protoprint', src,
      str(dst),
      './bazel-bin/tools/protoxform/protoprint.runfiles/envoy/tools/type_whisperer/api_type_db.pb_text'
  ])


def MergeActiveShadow(active_src, shadow_src, dst):
  """Merge active/shadow FileDescriptorProto to a destination file.

  Args:
    active_src: source path for active FileDescriptorProto.
    shadow_src: source path for active FileDescriptorProto.
    dst: destination path for FileDescriptorProto.
  """
  print('MergeActiveShadow %s' % dst)
  subprocess.check_output([
      'bazel-bin/tools/protoxform/merge_active_shadow',
      active_src,
      shadow_src,
      dst,
  ])


def SyncProtoFile(dst_srcs):
  """Pretty-print a proto descriptor from protoxform.py Bazel cache artifacts."

  In the case where we are generating an Envoy internal shadow, it may be
  necessary to combine the current active proto, subject to hand editing, with
  shadow artifacts from the previous verion; this is done via
  MergeActiveShadow().

  Args:
    dst_srcs: destination/sources path tuple.
  """
  dst, srcs = dst_srcs
  assert (len(srcs) > 0)
  # If we only have one candidate source for a destination, just pretty-print.
  if len(srcs) == 1:
    src = srcs[0]
    ProtoPrint(src, dst)
  else:
    # We should only see an active and next major version candidate from
    # previous version today.
    assert (len(srcs) == 2)
    shadow_srcs = [
        s for s in srcs if s.endswith('.next_major_version_candidate.envoy_internal.proto')
    ]
    active_src = [s for s in srcs if s.endswith('active_or_frozen.proto')][0]
    # If we're building the shadow, we need to combine the next major version
    # candidate shadow with the potentially hand edited active version.
    if len(shadow_srcs) > 0:
      assert (len(shadow_srcs) == 1)
      with tempfile.NamedTemporaryFile() as f:
        MergeActiveShadow(active_src, shadow_srcs[0], f.name)
        ProtoPrint(f.name, dst)
    else:
      ProtoPrint(active_src, dst)
    src = active_src
  rel_dst_path = GetDestinationPath(src)
  return ['//%s:pkg' % str(rel_dst_path.parent)]


def GetImportDeps(proto_path):
  """Obtain the Bazel dependencies for the import paths from a .proto file.

  Args:
    proto_path: path to .proto.

  Returns:
    A list of Bazel targets reflecting the imports in the .proto at proto_path.
  """
  imports = []
  with open(proto_path, 'r', encoding='utf8') as f:
    for line in f:
      match = re.match(IMPORT_REGEX, line)
      if match:
        import_path = match.group(1)
        # We can ignore imports provided implicitly by api_proto_package().
        if any(import_path.startswith(p) for p in API_BUILD_SYSTEM_IMPORT_PREFIXES):
          continue
        # Special case handling for UDPA annotations.
        if import_path.startswith('udpa/annotations/'):
          imports.append('@com_github_cncf_udpa//udpa/annotations:pkg')
          continue
        # Special case handling for UDPA core.
        if import_path.startswith('udpa/core/v1/'):
          imports.append('@com_github_cncf_udpa//udpa/core/v1:pkg')
          continue
        # Explicit remapping for external deps, compute paths for envoy/*.
        if import_path in external_proto_deps.EXTERNAL_PROTO_IMPORT_BAZEL_DEP_MAP:
          imports.append(external_proto_deps.EXTERNAL_PROTO_IMPORT_BAZEL_DEP_MAP[import_path])
          continue
        if import_path.startswith('envoy/'):
          # Ignore package internal imports.
          if os.path.dirname(proto_path).endswith(os.path.dirname(import_path)):
            continue
          imports.append('//%s:pkg' % os.path.dirname(import_path))
          continue
        raise ProtoSyncError(
            'Unknown import path mapping for %s, please update the mappings in tools/proto_sync.py.\n'
            % import_path)
  return imports


def GetPreviousMessageTypeDeps(proto_path):
  """Obtain the Bazel dependencies for the previous version of messages in a .proto file.

  We need to link in earlier proto descriptors to support Envoy reflection upgrades.

  Args:
    proto_path: path to .proto.

  Returns:
    A list of Bazel targets reflecting the previous message types in the .proto at proto_path.
  """
  contents = pathlib.Path(proto_path).read_text(encoding='utf8')
  matches = re.findall(PREVIOUS_MESSAGE_TYPE_REGEX, contents)
  deps = []
  for m in matches:
    target = '//%s:pkg' % GetDirectoryFromPackage(m)
    deps.append(target)
  return deps


def HasServices(proto_path):
  """Does a .proto file have any service definitions?

  Args:
    proto_path: path to .proto.

  Returns:
    True iff there are service definitions in the .proto at proto_path.
  """
  with open(proto_path, 'r', encoding='utf8') as f:
    for line in f:
      if re.match(SERVICE_REGEX, line):
        return True
  return False


# Key sort function to achieve consistent results with buildifier.
def BuildOrderKey(key):
  return key.replace(':', '!')


def BuildFileContents(root, files):
  """Compute the canonical BUILD contents for an api/ proto directory.

  Args:
    root: base path to directory.
    files: a list of files in the directory.

  Returns:
    A string containing the canonical BUILD file content for root.
  """
  import_deps = set(sum([GetImportDeps(os.path.join(root, f)) for f in files], []))
  history_deps = set(sum([GetPreviousMessageTypeDeps(os.path.join(root, f)) for f in files], []))
  deps = import_deps.union(history_deps)
  has_services = any(HasServices(os.path.join(root, f)) for f in files)
  fields = []
  if has_services:
    fields.append('    has_services = True,')
  if deps:
    if len(deps) == 1:
      formatted_deps = '"%s"' % list(deps)[0]
    else:
      formatted_deps = '\n' + '\n'.join(
          '        "%s",' % dep for dep in sorted(deps, key=BuildOrderKey)) + '\n    '
    fields.append('    deps = [%s],' % formatted_deps)
  formatted_fields = '\n' + '\n'.join(fields) + '\n' if fields else ''
  return BUILD_FILE_TEMPLATE.substitute(fields=formatted_fields)


def SyncBuildFiles(cmd, dst_root):
  """Diff or in-place update api/ BUILD files.

  Args:
    cmd: 'check' or 'fix'.
  """
  for root, dirs, files in os.walk(str(dst_root)):
    is_proto_dir = any(f.endswith('.proto') for f in files)
    if not is_proto_dir:
      continue
    build_contents = BuildFileContents(root, files)
    build_path = os.path.join(root, 'BUILD')
    with open(build_path, 'w') as f:
      f.write(build_contents)


def GenerateCurrentApiDir(api_dir, dst_dir):
  """Helper function to generate original API repository to be compared with diff.
  This copies the original API repository and deletes file we don't want to compare.

  Args:
    api_dir: the original api directory
    dst_dir: the api directory to be compared in temporary directory
  """
  shutil.copytree(str(api_dir.joinpath("pb")), str(dst_dir.joinpath("pb")))
  dst = dst_dir.joinpath("envoy")
  shutil.copytree(str(api_dir.joinpath("envoy")), str(dst))

  for p in dst.glob('**/*.md'):
    p.unlink()


def GitStatus(path):
  return subprocess.check_output(['git', 'status', '--porcelain', str(path)]).decode()


def GitModifiedFiles(path, suffix):
  """Obtain a list of modified files since the last commit merged by GitHub.

  Args:
    path: path to examine.
    suffix: path suffix to filter with.
  Return:
    A list of strings providing the paths of modified files in the repo.
  """
  try:
    modified_files = subprocess.check_output(
        ['tools/git/modified_since_last_github_commit.sh', 'api', 'proto']).decode().split()
    return modified_files
  except subprocess.CalledProcessError as e:
    if e.returncode == 1:
      return []
    raise


# If we're not forcing format, i.e. FORCE_PROTO_FORMAT=yes, in the environment,
# then try and see if we can skip reformatting based on some simple path
# heuristics. This saves a ton of time, since proto format and sync is not
# running under Bazel and can't do change detection.
def ShouldSync(path, api_proto_modified_files, py_tools_modified_files):
  if os.getenv('FORCE_PROTO_FORMAT') == 'yes':
    return True
  # If tools change, safest thing to do is rebuild everything.
  if len(py_tools_modified_files) > 0:
    return True
  # Check to see if the basename of the file has been modified since the last
  # GitHub commit. If so, rebuild. This is safe and conservative across package
  # migrations in v3 and v4alpha; we could achieve a lower rate of false
  # positives if we examined package migration annotations, at the expense of
  # complexity.
  for p in api_proto_modified_files:
    if os.path.basename(p) in path:
      return True
  # Otherwise we can safely skip syncing.
  return False


def Sync(api_root, mode, labels, shadow):
  api_proto_modified_files = GitModifiedFiles('api', 'proto')
  py_tools_modified_files = GitModifiedFiles('tools', 'py')
  with tempfile.TemporaryDirectory() as tmp:
    dst_dir = pathlib.Path(tmp).joinpath("b")
    paths = []
    for label in labels:
      paths.append(utils.BazelBinPathForOutputArtifact(label, '.active_or_frozen.proto'))
      paths.append(
          utils.BazelBinPathForOutputArtifact(
              label, '.next_major_version_candidate.envoy_internal.proto'
              if shadow else '.next_major_version_candidate.proto'))
    dst_src_paths = defaultdict(list)
    for path in paths:
      if os.stat(path).st_size > 0:
        abs_dst_path, rel_dst_path = GetAbsRelDestinationPath(dst_dir, path)
        if ShouldSync(path, api_proto_modified_files, py_tools_modified_files):
          dst_src_paths[abs_dst_path].append(path)
        else:
          print('Skipping sync of %s' % path)
          src_path = str(pathlib.Path(api_root, rel_dst_path))
          shutil.copy(src_path, abs_dst_path)
    with mp.Pool() as p:
      pkg_deps = p.map(SyncProtoFile, dst_src_paths.items())
    SyncBuildFiles(mode, dst_dir)

    current_api_dir = pathlib.Path(tmp).joinpath("a")
    current_api_dir.mkdir(0o755, True, True)
    api_root_path = pathlib.Path(api_root)
    GenerateCurrentApiDir(api_root_path, current_api_dir)

    # These support files are handled manually.
    for f in [
        'envoy/annotations/resource.proto', 'envoy/annotations/deprecation.proto',
        'envoy/annotations/BUILD'
    ]:
      copy_dst_dir = pathlib.Path(dst_dir, os.path.dirname(f))
      copy_dst_dir.mkdir(exist_ok=True)
      shutil.copy(str(pathlib.Path(api_root, f)), str(copy_dst_dir))

    diff = subprocess.run(['diff', '-Npur', "a", "b"], cwd=tmp, stdout=subprocess.PIPE).stdout

    if diff.strip():
      if mode == "check":
        print("Please apply following patch to directory '{}'".format(api_root), file=sys.stderr)
        print(diff.decode(), file=sys.stderr)
        sys.exit(1)
      if mode == "fix":
        git_status = GitStatus(api_root)
        if git_status:
          print('git status indicates a dirty API tree:\n%s' % git_status)
          print(
              'Proto formatting may overwrite or delete files in the above list with no git backup.'
          )
          if input('Continue? [yN] ').strip().lower() != 'y':
            sys.exit(1)
        src_files = set(str(p.relative_to(current_api_dir)) for p in current_api_dir.rglob('*'))
        dst_files = set(str(p.relative_to(dst_dir)) for p in dst_dir.rglob('*'))
        deleted_files = src_files.difference(dst_files)
        if deleted_files:
          print('The following files will be deleted: %s' % sorted(deleted_files))
          print(
              'If this is not intended, please see https://github.com/envoyproxy/envoy/blob/master/api/STYLE.md#adding-an-extension-configuration-to-the-api.'
          )
          if input('Delete files? [yN] ').strip().lower() == 'y':
            subprocess.run(['patch', '-p1'], input=diff, cwd=str(api_root_path.resolve()))
          else:
            sys.exit(1)
        else:
          subprocess.run(['patch', '-p1'], input=diff, cwd=str(api_root_path.resolve()))


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument('--mode', choices=['check', 'fix'])
  parser.add_argument('--api_root', default='./api')
  parser.add_argument('--api_shadow_root', default='./generated_api_shadow')
  parser.add_argument('labels', nargs='*')
  args = parser.parse_args()

  Sync(args.api_root, args.mode, args.labels, False)
  Sync(args.api_shadow_root, args.mode, args.labels, True)
