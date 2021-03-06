from app.templating.summary.block import Block


class Group:

    def __init__(self, group_schema, path, answer_store, metadata, schema):
        self.id = group_schema['id']
        self.title = group_schema.get('title')
        self.blocks = self._build_blocks(group_schema, path, answer_store, metadata, schema)

    @staticmethod
    def _build_blocks(group_schema, path, answer_store, metadata, schema):
        blocks = []

        block_ids_on_path = [location.block_id for location in path]

        for block in group_schema['blocks']:
            if block['id'] in block_ids_on_path and \
                    block['type'] == 'Question':
                blocks.extend([Block(block, group_schema['id'], answer_store, metadata, schema).serialize()])

        return blocks

    def serialize(self):
        return {
            'id': self.id,
            'title': self.title,
            'blocks': self.blocks,
        }
