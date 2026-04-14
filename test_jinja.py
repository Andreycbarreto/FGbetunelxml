from jinja2 import Template
t = Template("{{ items | rejectattr('val', 'none') | sum(attribute='val') }}")
print(t.render(items=[{'val': 10}, {'val': None}, {'val': 20}]))
