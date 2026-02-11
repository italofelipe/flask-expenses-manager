from __future__ import annotations

import graphene

from app.graphql.mutations import Mutation
from app.graphql.query import Query

schema = graphene.Schema(query=Query, mutation=Mutation)

__all__ = ["schema", "Query", "Mutation"]
