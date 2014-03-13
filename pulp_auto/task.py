import item, time, hasdata
from item import (Item, GroupItem)
from pulp_auto.pulp import Request
from pulp_auto import strip_url

class TaskFailure(RuntimeError):
    def __init__(self, *args, **kvs):
        self.task = kvs.pop('task', None)
        super(TaskFailure, self).__init__(*args, **kvs)


class AbstractTask(object):
    state = None
    active_states = []
    end_states = []
    error_state = []

    def update(self, pulp):
        '''an abstract update does nothing'''
        pass

    def wait(self, pulp, timeout=60, frequency=0.5):
        '''wait while all of these conditions hold:
             - self.state in self.active_states
             - self.state not in self.end_states
             - timeout not elapsed yet
        '''
        delta = time.time() + timeout
        while self.state not in self.end_states and self.state in self.active_states and time.time() <= delta:
            time.sleep(frequency)
            try:
                self.reload(pulp)
                if self.state in self.error_state:
                    raise TaskFailure('Task failed: %r' % self.data['reasons'], task=self)
            except AssertionError as e:
                # task gone --- no need to wait anymore
                # FIXME: doesn't work with group-tasks, dunno why they can't be accessed via
                # /tasks_group/<task.group_id>/<task.task_id>/
                break


class TaskDetails(hasdata.HasData):
    relevant_data_keys = [
        "response",
        "reasons",
        "state",
        "task_id",
        "task_group_id",
        "schedule_id",
        "progress",
        "result",
        "exception",
        "traceback",
        "start_time",
        "finish_time",
        "tags"
    ]
    required_data_keys = ['task_id', 'state']
    active_states = ['running', 'waiting']
    end_states = ['finished']
    error_state = ['error']

    @property
    def state(self):
        return self.data['state']

    @property
    def id(self):
        return self.data['task_id']

    @id.setter
    def id(self, other):
        self.data['task_id'] = other


class Task(TaskDetails, AbstractTask, Item):
    '''an item-view task'''
    path = '/tasks/'

    @classmethod
    def wait_for_response(cls, pulp, response):
        '''a shortcut for wait & from_response'''
        ret = cls.from_response(response)
        if isinstance(ret, list):
            # more than one task pending
            for task in ret:
                task.wait(pulp)
        else:
            ret.wait(pulp)

    @classmethod
    def wait_for_report(cls, pulp, response):
        # now every asyncronous call returns a call report object
        # call report has 'spawned_tasks' that contains list of tasks
        # meanwhile every tasks can have its own spawned tasks
        ret = response.json()['spawned_tasks']
        if isinstance(ret, list):
            for task in ret:
                task_resp = pulp.send(Request('GET', strip_url(task['_href'])))
                Task.wait_for_response(pulp, task_resp)
                task_resp = pulp.send(Request('GET', strip_url(task['_href'])))
                if 'spawned_tasks' in Task.from_response(task_resp).data:
                    Task.wait_for_report(pulp, task_resp)


TASK_DATA_EXAMPLE = {
    "_href": "/pulp/api/v2/tasks/7744e2df-39b9-46f0-bb10-feffa2f7014b/",
    "response": "postponed",
    "reasons": [{"resource_type": "repository", "resource_id": "test-repo", "operation": "update"}],
    "state": "running",
    "task_id": "7744e2df-39b9-46f0-bb10-feffa2f7014b",
    "task_group_id": None,
    "schedule_id": None,
    "progress": {},
    "result": None,
    "exception": None,
    "traceback": None,
    "start_time": "2012-05-13T23:00:02Z",
    "finish_time": None,
    "tags": ["pulp:repository:test-repo"],
}
