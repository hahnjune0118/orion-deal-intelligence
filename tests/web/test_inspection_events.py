"""Fresh grid intent takes precedence over redundant document render events."""
from pathlib import Path
import pytest

pytestmark=pytest.mark.integration
ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def endpoint():
    from orion.app import create_app
    app=create_app(project_root=ROOT,secret_key='inspection-event-test-secret-32-bytes')
    client=app.server.test_client();client.get('/')
    with client.session_transaction() as session:sid=session['orion_session']
    workspace=app.server.extensions['orion_workspace'];token=workspace.new('lm',sid)
    view=workspace.view(token,sid)
    return app,client,token,view


def send(endpoint,output_name,values,changed):
    app,client,_,_=endpoint
    key=output_name if output_name in app.callback_map else next(k for k in app.callback_map if output_name in k)
    callback=app.callback_map[key];outputs=callback['output']
    encode=lambda item:dict(id=item.component_id,property=item.component_property)
    payload=dict(output=key,outputs=[encode(o) for o in outputs] if isinstance(outputs,list) else encode(outputs),
                 inputs=[{**i,'value':values.get(f"{i['id']}.{i['property']}")} for i in callback['inputs']],
                 state=[{**i,'value':values.get(f"{i['id']}.{i['property']}")} for i in callback['state']],changedPropIds=changed)
    response=client.post('/_dash-update-component',json=payload,headers={'Origin':'http://localhost'})
    assert response.status_code in {200,204},response.data.decode()
    return response.get_json()['response'] if response.status_code==200 else {}


def identifiers(value):
    if isinstance(value,dict):
        if value.get('props',{}).get('className')=='identifier':yield value['props']['children']
        for child in value.values():yield from identifiers(child)
    elif isinstance(value,list):
        for child in value:yield from identifiers(child)


def values(endpoint):
    _,_,token,view=endpoint
    return {'workspace-token.data':token,'document-selector.value':view['documents'][0]['id'],
            'deal-selector.value':'lm','question-grid.selectedRows':[{'id':'q_lm_labor'}],
            'question-grid.cellClicked':{'rowId':'q_lm_labor','data':{'id':'q_lm_labor'}}}


@pytest.mark.parametrize('event',['cellClicked','selectedRows'])
def test_question_event_wins_when_document_is_published_in_same_batch(endpoint,event):
    result=send(endpoint,'source-inspector.children',values(endpoint),['document-selector.value','question-grid.'+event])
    assert list(identifiers(result))[0]=='q_lm_labor'


def test_explicit_document_change_ignores_a_stale_question_click(endpoint):
    data=values(endpoint)
    result=send(endpoint,'source-inspector.children',data,['document-selector.value'])
    assert list(identifiers(result))[0]==data['document-selector.value']


def test_grid_mount_does_not_erase_the_current_inspection(endpoint):
    data=values(endpoint);data['question-grid.selectedRows']=[];data['question-grid.cellClicked']=None
    result=send(endpoint,'source-inspector.children',data,['question-grid.selectedRows'])
    assert 'source-inspector' not in result


def test_page_render_does_not_republish_an_unchanged_document(endpoint):
    data=values(endpoint);data.update({'workspace-tabs.value':'questions','event-selector.value':None})
    result=send(endpoint,'deal-heading.children',data,['workspace-tabs.value'])
    assert 'document-selector' in result
    assert 'options' in result['document-selector']
    assert 'value' not in result['document-selector']
