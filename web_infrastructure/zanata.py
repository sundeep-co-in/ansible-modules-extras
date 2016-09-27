#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2016, Sundeep Anand <suanand@redhat.com>
#
# This file is part of Ansible.
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = """
module: zanata
short_description: Manage Zanata Projects.
description:
  - Manage Zanata projects by using Zanata REST API.
  - View project details and stats.
  - Fetch zanata.xml config for project_version.
version_added: '2.2'
author: 'Sundeep Anand (@sundeep_co_in)'
options:
  operation:
    required: true
    aliases: [ command ]
    choices: [ create_project, create_version, detail, modify, stats, config ]
    description:
      - The operation to perform.

  url:
    required: false
    description:
      - Base URL of the Zanata instance.
    default: http://localhost:8080/zanata

  username:
    required: false
    description:
      - Zanata username to access API with.

  token:
    required: false
    description:
      - Zanata API key for write operations.

  project_id:
    aliases: [ prj ]
    required: true
    description:
      - Zanata project id.

  project_name:
    required: false
    description:
      - Zanata project name.

  description:
    aliases: [ desc ]
    required: false
    description:
     - Project description, in short.

  type:
    required: false
    choices: [ file, gettext, podir, properties, utf8properties, xliff, xml ]
    description:
     - Project type, for content handling.
    default: file

  version:
    required: false
    aliases: [ ver, iter ]
    description:
     - Zanata project version

notes:
  - "Write operations would require Zanata API key."

"""

EXAMPLES = """
---
- hosts: localhost
  vars:
      server: https://translate.zanata.org
      user: zanata_user
      key: hsfp37498hfkjdshfk
      project: ZNTAPRJID
      version: ZNTAPRJVER

  tasks:
      # View project details
      - name: Project details
        zanata: operation=detail url={{ server }} prj={{ project }}
        register: project_details

      - name: Project translation stats
        zanata: operation=stats url={{ server }}
                prj={{ project }} version={{ version }}
        register: project_stats

      # Create or modify a project
      - name: Create a project
        zanata: url={{ server }} username={{ user }} token={{ key }}
                operation=create_project type=gettext
                prj={{ project }} project_name="PROJECT NAME"
                desc="Created using Ansible"

      - name: Modify a project
        zanata: url={{ server }} username={{ user }} token={{ key }}
                operation=modify type=file prj={{ project }}
                project_name="NEW PRJ" desc="Modified using Ansible"

      # Create a project version
      - name: Create a project version
        zanata: url={{ server }} username={{ user }} token={{ key }}
                operation=create_version prj={{ project }}
                version={{ version }}

      # View project version config
      - name: View project version config
        zanata: url={{ server }} operation=config
                prj={{ project }} version={{ version }}
        register: project_config

"""

RETURN = """
msg = 'Creation successful!'
msg = 'Modification successful!'
Zanata project details, stats json
Zanata project config xml
"""

import sys

try:
    import json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        # let module_utils/basic.py raise an error here
        pass

from ansible.module_utils.basic import *
from ansible.module_utils.urls import *
from ansible.module_utils.pycompat24 import get_exception


def rest_call(url, user=None, token=None, data=None, method=None, op=None):
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if user and token:
        headers.update({
            'X-Auth-User': user, 'X-Auth-Token': token
        })

    if data:
        data = json.dumps(data)

    if op == 'config':
        headers['Accept'] = 'application/xml'

    module.params['follow_redirects'] = True
    response, info = fetch_url(module, url, data=data,
                               method=method, headers=headers)

    if info['status'] not in (200, 201, 204):
        module.fail_json(msg=info['msg'])
    elif info['status'] == 201 and op == 'create':
        return 'Creation successful!'
    elif info['status'] == 200 and op == 'modify':
        return 'Modification successful!'

    body = response.read()

    if body and op == 'config':
        return body
    elif body:
        return json.loads(body)
    else:
        return {}


def create_project(base_url, params, op_modify=False):
    body = {
        "name": params['project_name'], "id": params['project_id'],
        "description": params['description'], "type": params['type']
    }
    zanata_user = params['username']
    api_key = params['token']
    url = base_url + '/projects/p/' + params['project_id']
    operation = 'create'
    if op_modify:
        operation = 'modify'
    return rest_call(
        url, user=zanata_user, token=api_key, data=body,
        method='PUT', op=operation
    )


def modify(base_url, params):
    create_project(base_url, params, op_modify=True)


def create_version(base_url, params):
    body = {"id": params['version']}
    zanata_user = params['username']
    api_key = params['token']
    url = base_url + '/project/' + params['project_id'] + \
          '/version/' + params['version']
    return rest_call(url, user=zanata_user, token=api_key,
                     data=body, method='PUT', op='create')


def stats(base_url, params):
    url = base_url + '/stats/proj/' + params['project_id'] + \
          '/iter/' + params['version']
    return rest_call(url, method='GET')


def detail(base_url, params):
    url = base_url + '/projects/p/' + params['project_id']
    return rest_call(url, method='GET')


def config(base_url, params):
    url = base_url + '/project/' + params['project_id'] + \
          '/version/' + params['version'] + '/config'
    return rest_call(url, method='GET', op='config')


def prepare_exit_json(command, server_return):
    exit_json_dict = {}
    if command in ('create_project', 'create_version', 'modify'):
        exit_json_dict['changed'] = True
    if server_return:
        exit_json_dict['msg'] = server_return
    return exit_json_dict


# Some parameters are required depending on the command:
PARAMS_REQUIRED = dict(
    create_project=['url', 'project_id', 'project_name', 'username',
                    'token', 'description', 'type'],
    create_version=['url', 'project_id', 'version', 'username', 'token'],
    detail=['url', 'project_id'],
    modify=['url', 'project_id', 'project_name', 'username', 'token',
            'description', 'type'],
    stats=['url', 'project_id', 'version'],
    config=['url', 'project_id', 'version'],
)

def main():
    global module
    module = AnsibleModule(
        argument_spec=dict(
            operation   =   dict(required=True,
                                 choices=['create_project', 'create_version',
                                          'detail', 'modify', 'stats', 'config'],
                                 aliases=['command']),
            url         =   dict(required=False, default="http://localhost:8080/zanata"),
            project_id  =   dict(required=True, aliases=['prj']),
            project_name=   dict(required=False),
            username    =   dict(required=False),
            token       =   dict(required=False, no_log=True),
            description =   dict(required=False, aliases=['desc']),
            type        =   dict(required=False,
                                 choices=['file', 'gettext', 'podir', 'properties',
                                          'utf8properties', 'xliff', 'xml'],
                                 default="file"),
            version     =   dict(required=False, aliases=['ver', 'iter']),
        ),
        supports_check_mode=False
    )

    command = module.params['operation']

    # Check for required params
    missing = []
    for param in PARAMS_REQUIRED[command]:
        if not module.params[param]:
            missing.append(param)
    if missing:
        module.fail_json(
            msg="[ %s ] operation requires: %s" % (command, ", ".join(missing))
        )

    url = module.params['url']
    if not url.endswith('/'):
        url = url+'/'
    base_url = url + 'rest'

    # perform operation
    try:
        this_module = sys.modules[__name__]
        method = getattr(this_module, command)
        server_return = method(base_url, module.params)
    except Exception:
        e = get_exception()
        return module.fail_json(msg=e.message)

    # exit with success json
    module.exit_json(**prepare_exit_json(command, server_return))


if __name__ == '__main__':
    main()
