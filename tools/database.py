from aiohttp import web
import asyncio, json, socket
import signal
import json
import traceback
from peewee import SqliteDatabase, Model, BlobField, CharField, TextField, IntegerField, CompositeKey, DoesNotExist, IntegrityError
Checksum = lambda *args, **kwargs: BlobField(*args, **kwargs)

db = SqliteDatabase(None)

# from the Seamless code
def parse_checksum(checksum, as_bytes=False):
    """Parses checksum and returns it as string"""
    if isinstance(checksum, bytes):
        checksum = checksum.hex()
    if isinstance(checksum, str):
        checksum = bytes.fromhex(checksum)

    if isinstance(checksum, bytes):
        assert len(checksum) == 32, len(checksum)
        if as_bytes:
            return checksum
        else:
            return checksum.hex()
    
    if checksum is None:
        return
    raise TypeError(type(checksum))

# from the Seamless code
class SeamlessBufferInfo:
    __slots__ = (
        "checksum", "length", "is_utf8", "is_json", "json_type", 
        "is_json_numeric_array", "is_json_numeric_scalar",
        "is_numpy", "dtype", "shape", "is_seamless_mixed", 
        "str2text", "text2str", "binary2bytes", "bytes2binary",
        "binary2json", "json2binary"
    )
    def __init__(self, checksum, params:dict={}):
        for slot in self.__slots__:
            setattr(self, slot, params.get(slot))
        if isinstance(checksum, str):
            checksum = bytes.fromhex(checksum)
        self.checksum = checksum
    
    def __setattr__(self, attr, value):
        if value is not None:    
            if attr == "length":
                if not isinstance(value, int):
                    raise TypeError(type(value))
                if not value >= 0:
                    raise ValueError
            if attr.startswith("is_"):
                if not isinstance(value, bool):
                    raise TypeError(type(value))
        if attr.find("2") > -1 and value is not None:
            if isinstance(value, bytes):
                value = value.hex()
        super().__setattr__(attr, value)

    def __setitem__(self, item, value):
        return setattr(self, item, value)

    def __getitem__(self, item):
        return getattr(self, item)

    def update(self, other):
        if not isinstance(other, SeamlessBufferInfo):
            raise TypeError
        for attr in self.__slots__:
            v = getattr(other, attr)
            if v is not None:
                setattr(self, attr, v)
    
    def get(self, attr, default=None):
        value = getattr(self, attr)
        if value is None:
            return default
        else:
            return value
    
    def as_dict(self):
        result = {}
        for attr in self.__slots__:
            if attr == "checksum":
                continue
            v = getattr(self, attr)
            if v is not None:
                result[attr] = v
        return result


class BaseModel(Model):
    class Meta:
        database = db
        legacy_table_names = False
    
    @classmethod
    def create(cls, **kwargs):
        try:
            return super().create(**kwargs)
        except IntegrityError:
            prim = primary[cls]
            instance = cls.get(**{prim: kwargs[prim]})
            instance.update(**kwargs)
            instance.save()

class Transformation(BaseModel):
    checksum = Checksum(primary_key=True)
    result = Checksum(index=True, unique=False)

print("""
REDESIGN: elisions will give checksums instead of JSON results (requires buffer retrieval)
  => dict of (celltype, hash_pattern, checksum) entries, see def "get_elision_result"
""")

class Elision(BaseModel):
    checksum = Checksum(primary_key=True)
    result = Checksum()

class BufferInfo(BaseModel):
    # store SeamlessBufferInfo as JSON
    checksum = Checksum(primary_key=True)
    buffer_info = TextField()

class SyntacticToSemantic(BaseModel):
    syntactic = Checksum(primary_key=True)
    celltype = TextField()
    subcelltype = TextField()
    semantic = Checksum()

class Compilation(BaseModel):
    checksum = Checksum(primary_key=True)
    result = Checksum(index=True)

class Expression(BaseModel):
    
    input_checksum = Checksum()
    path = CharField(max_length=100)
    celltype = CharField(max_length=20)
    hash_pattern = CharField(max_length=20)
    target_celltype = CharField(max_length=20)
    target_hash_pattern = CharField(max_length=20)
    result = Checksum(index=True, unique=False)
    class Meta:
            database = db
            legacy_table_names = False
            primary_key = CompositeKey(
                'input_checksum', 'path', 'celltype', 'hash_pattern',
                'target_celltype', 'target_hash_pattern'
            )
    
    @classmethod
    def create(cls, **kwargs):
        try:
            return super().create(**kwargs)
        except IntegrityError:
            kwargs2 = {}
            for k in (
                'input_checksum', 'path', 'celltype', 'hash_pattern',
                'target_celltype', 'target_hash_pattern'
            ):
                kwargs2[k] = kwargs[l]
            instance = cls.get(**kwargs2)
            instance["result"] = kwargs["result"]
            instance.save()

class StructuredCellJoin(BaseModel):
    '''
    Structured cell join:
    input checksum: checksum of a tuple containing:
    - auth: auth checksum
    - inchannels: dict-of-checksums where key=inchannel and value=checksum
    - schema: schema checksum
    result: value checksum of the structured cell
    '''
    checksum = Checksum(primary_key=True)
    result = Checksum(index=True, unique=False)


class MetaData(BaseModel):
    # store opaque meta-data (JSON) for transformations:
    # - executor name (null, seamless-run-transformation, SLURM, ...)
    # - Seamless version (including Docker/Singularity/conda version)
    # - exact environment conda packages (as environment checksum)
    # - hardware (GPU, memory)
    # - execution time (also if failed)
    # - last recorded progress (if failed)
    checksum = Checksum(primary_key=True)
    metadata = TextField()

model_classes = [Transformation, Elision, BufferInfo, SyntacticToSemantic, Compilation, Expression, StructuredCellJoin, MetaData]
primary = {}
for model_class in model_classes:
    if model_class is Expression:
        continue
    for fieldname, field in model_class._meta.fields.items():
        if field.primary_key:
            primary[model_class] = fieldname
            break
    else:
        raise Exception


def err(*args, **kwargs):
    print("ERROR: " + args[0], *args[1:], **kwargs)
    exit(1)


class DatabaseError(Exception):
    pass

def is_port_in_use(address, port): # KLUDGE: For some reason, websockets does not test this??
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0

types = (
    "protocol",
    "delete_key",
    "delete_semantic_to_syntactic",
    "buffer_info",
    "semantic_to_syntactic",
    "compilation",
    "transformation",
    "elision",
    "metadata",
    "expression",
    "structured_cell_join",
)

key_types = {
    "buffer_info": BufferInfo,
    "compilation": Compilation,
    "transformation": Transformation,
    "elision": Elision,
    "metadata": MetaData,
    "expression": Expression,
    "structured_cell_join": StructuredCellJoin,
}

def format_response(response, *, none_as_404=False):
    status = None
    if response is None:
        if not none_as_404:
            status = 400
            response = "ERROR: No response"
        else:
            status = 404
            response = "ERROR: Unknown key"
    elif isinstance(response, (bool, dict, list)):
        response = json.dumps(response)
    elif not isinstance(response, (str, bytes)):
        status = 400
        print("ERROR: wrong response format")
        print(type(response), response)
        print("/ERROR: wrong response format")
        response = "ERROR: wrong response format"
    return status, response


class DatabaseServer:
    future = None
    PROTOCOL = ("seamless", "database", "0.3")
    def __init__(self, host, port):
        self.host = host
        self.port = port

    async def _start(self):
        if is_port_in_use(self.host, self.port): # KLUDGE
            print("ERROR: %s port %d already in use" % (self.host, self.port))
            raise Exception

        app = web.Application(client_max_size=10e9)
        app.add_routes([
            web.get('/{tail:.*}', self._handle_get),
            web.put('/{tail:.*}', self._handle_put),
        ])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

    def start(self):
        if self.future is not None:
            return
        coro = self._start()
        self.future = asyncio.ensure_future(coro)

    async def _handle_get(self, request):
        try:
            #print("NEW GET REQUEST", hex(id(request)))
            data = await request.read()
            #print("NEW GET REQUEST", data)
            status = 200
            type = None
            try:
                try:
                    rq = json.loads(data)
                except Exception:
                    raise DatabaseError("Malformed request") from None
                #print("NEW GET REQUEST DATA", rq)
                try:
                    type = rq["type"]
                    if type not in types:
                        raise KeyError
                    if type != "protocol":
                        checksum = rq["checksum"]
                except KeyError:
                    raise DatabaseError("Malformed request") from None

                if type == "protocol":
                    response = list(self.PROTOCOL)
                else:
                    try:
                        checksum = parse_checksum(checksum, as_bytes=True)
                    except ValueError:
                        #import traceback; traceback.print_exc()
                        raise DatabaseError("Malformed request") from None
                    response = await self._get(type, checksum, rq)
            except DatabaseError as exc:
                status = 400
                if exc.args[0] == "Unknown key":
                    status = 404
                response = "ERROR: " + exc.args[0]
            status2, response = format_response(response, none_as_404=True)
            if status == 200 and status2 is not None:
                status = status2
            ###if status != 200: print(response)
            return web.Response(
                status=status,
                body=response
            )
        finally:
            #print("END GET REQUEST", hex(id(request)))
            pass

    async def _handle_put(self, request):
        try:
            #print("NEW PUT REQUEST", hex(id(request)))
            data = await request.read()
            #print("NEW PUT REQUEST", data)
            status = 200
            try:
                try:
                    rq = json.loads(data)
                except Exception:
                    import traceback; traceback.print_exc()
                    #raise DatabaseError("Malformed request") from None
                if not isinstance(rq, dict):
                    #import traceback; traceback.print_exc()
                    raise DatabaseError("Malformed request")

                #print("NEW PUT REQUEST DATA", rq)
                try:
                    type = rq["type"]
                    if type not in types:
                        raise KeyError
                    checksum = rq["checksum"]
                except KeyError:
                    #import traceback; traceback.print_exc()
                    raise DatabaseError("Malformed request") from None
                 
                try:
                    checksum = parse_checksum(checksum, as_bytes=True)
                except ValueError:
                    #import traceback; traceback.print_exc()
                    raise DatabaseError("Malformed request") from None

                response = await self._set(type, checksum, rq)
            except DatabaseError as exc:
                status = 400
                response = "ERROR: " + exc.args[0]
            status2, response = format_response(response)
            if status == 200 and status2 is not None:
                status = status2
            #if status != 200: print(response)
            return web.Response(
                status=status,
                body=response
            )
        finally:
            #print("END PUT REQUEST", hex(id(request)))
            pass

    async def _get(self, type, checksum, request):
        if type == "buffer_info":
            try:
                return json.loads(BufferInfo[checksum].buffer_info)
            except DoesNotExist:
                raise DatabaseError("Unknown key") from None
            

        elif type == "semantic_to_syntactic":
            try:
                celltype, subcelltype = request["celltype"], request["subcelltype"]
            except KeyError:
                raise DatabaseError("Malformed semantic-to-syntactic request")
            results = SyntacticToSemantic.select().where(
                SyntacticToSemantic.semantic==checksum,
                SyntacticToSemantic.celltype==celltype,
                SyntacticToSemantic.subcelltype==subcelltype
            ).execute()
            if results:
                return [parse_checksum(result.syntactic) for result in results]
            raise DatabaseError("Unknown key")

        elif type == "compilation":
            try:
                return parse_checksum(Compilation[checksum].result)
            except DoesNotExist:
                return None # None is also a valid response
            
        elif type == "transformation":
            try:
                return parse_checksum(Transformation[checksum].result)
            except DoesNotExist:
                return None # None is also a valid response

        elif type == "elision":
            try:
                return parse_checksum(Elision[checksum].result)
            except DoesNotExist:
                return None # None is also a valid response

        elif type == "metadata":
            try:
                return json.loads(MetaData[checksum].metadata)
            except DoesNotExist:
                return None # None is also a valid response

        elif type == "expression":
            try:
                celltype = request["celltype"]
                path = json.dumps(request["path"])
                hash_pattern = json.dumps(request.get("hash_pattern", ""))
                target_celltype = request["target_celltype"]
                target_hash_pattern = json.dumps(request.get("target_hash_pattern", ""))
            except KeyError:
                raise DatabaseError("Malformed expression request")
            result = Expression.select().where(
                Expression.input_checksum == checksum,
                Expression.path==path,
                Expression.celltype==celltype,
                Expression.hash_pattern==hash_pattern,
                Expression.target_celltype==target_celltype,
                Expression.target_hash_pattern==target_hash_pattern
            ).execute()
            if not result:
                return None
            return parse_checksum(result[0].result)

        elif type == "structured_cell_join":
            try:
                return parse_checksum(StructuredCellJoin[checksum].result)
            except DoesNotExist:
                return None # None is also a valid response

        else:
            raise DatabaseError("Unknown request type")

    async def _set(self, type, checksum, request):
        if type == "delete_key":
            key_type = request["key_type"]
            try:
                key_type_class = key_types[key_type]
            except KeyError:
                raise DatabaseError("Malformed SET delete key request: invalid key_type") from None
            try:
                key_type_class[checksum].delete_instance()
                deleted = True
            except DoesNotExist:
                deleted = False
            return deleted

        elif type == "delete_syntactic_to_semantic":
            # TODO: test
            try:
                celltype, subcelltype, semantic = request["celltype"], request["subcelltype"], request["semantic"]
            except KeyError:
                raise DatabaseError("Malformed semantic-to-syntactic request") from None
            query = SyntacticToSemantic.delete().where(
                SyntacticToSemantic.syntactic==checksum,
                SyntacticToSemantic.celltype==celltype,
                SyntacticToSemantic.subcelltype==subcelltype,
                SyntacticToSemantic.semantic==semantic,
            )
            ndeleted = query.execute()
            return ndeleted

        elif type == "buffer_info":
            try:
                value = request["value"]
                if not isinstance(value, dict):
                    raise TypeError
                SeamlessBufferInfo(checksum, value)
                value = json.dumps(value, sort_keys=True, indent=2)
            except Exception:
                raise DatabaseError("Malformed SET buffer info request") from None            
            BufferInfo.create(checksum=checksum, buffer_info=value)

        elif type == "semantic_to_syntactic":
            try:
                value = request["value"]
                assert isinstance(value, list)
            except Exception:
                raise DatabaseError("Malformed SET semantic-to-syntactic request")
            try:
                celltype, subcelltype = request["celltype"], request["subcelltype"]
            except KeyError:
                raise DatabaseError("Malformed SET semantic-to-syntactic request") from None
            for semantic_checksum in value:
                with db.atomic():
                    SyntacticToSemantic.create(syntactic=checksum, celltype=celltype, subcelltype=subcelltype, semantic=semantic_checksum)
        
        elif type == "compilation":
            try:
                value = parse_checksum(request["value"], as_bytes=True)
            except (KeyError, ValueError):
                raise DatabaseError("Malformed SET compilation result request: value must be a checksum") from None
            Compilation.create(checksum=checksum, result=value)
        
        elif type == "transformation":
            try:
                value = parse_checksum(request["value"], as_bytes=True)
            except (KeyError, ValueError):
                raise DatabaseError("Malformed SET transformation result request: value must be a checksum") from None
            Transformation.create(checksum=checksum, result=value)

        elif type == "elision":
            try:
                value = parse_checksum(request["value"], as_bytes=True)
            except (KeyError, ValueError):
                raise DatabaseError("Malformed SET elision result request: value must be a checksum") from None
            Elision.create(checksum=checksum, result=value)

        elif type == "expression":
            try:
                value = parse_checksum(request["value"], as_bytes=True)
                celltype = request["celltype"]
                path = json.dumps(request["path"])
                hash_pattern = json.dumps(request.get("hash_pattern", ""))
                target_celltype = request["target_celltype"]
                target_hash_pattern = json.dumps(request.get("target_hash_pattern", ""))
            except KeyError:
                raise DatabaseError("Malformed expression request")
            try:
                #assert celltype in celltypes TODO? also for target_celltype
                assert len(path) <= 100
                if len(request["path"]):
                    assert celltype in ("mixed", "plain", "binary")
                assert len(celltype) <= 20
                assert len(hash_pattern) <= 20
                assert len(target_celltype) <= 20
                assert len(target_hash_pattern) <= 20
            except AssertionError:
                raise DatabaseError("Malformed expression request (constraint violation)")
            Expression.create(
                input_checksum=checksum,
                path=path,
                celltype=celltype,
                hash_pattern=hash_pattern,
                target_celltype=target_celltype,
                target_hash_pattern=target_hash_pattern,
                result=value
            )

        elif type == "structured_cell_join":
            try:
                value = parse_checksum(request["value"], as_bytes=True)
            except (KeyError, ValueError):
                raise DatabaseError("Malformed SET structured_cell_join request: value must be a checksum") from None
            StructuredCellJoin.create(checksum=checksum, result=value)

        elif type == "metadata":
            try:
                value = request["value"]
            except (KeyError, ValueError):
                raise DatabaseError("Malformed SET metadata request") from None
            value = json.dumps(value, sort_keys=True, indent=2)
            MetaData.create(checksum=checksum, metadata=value)

        else:
            raise DatabaseError("Unknown request type")
        return "OK"

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("database_file", help="""File where the database is stored.
The database contents are stored as a SQLite file.
If it doesn't exist, a new file is created.""")
    p.add_argument("--port", default=5522, type=int)
    p.add_argument("--host", default="0.0.0.0")
    args = p.parse_args()
    
    database_file = args.database_file
    db.init(database_file)
    db.connect()
    db.create_tables(model_classes, safe=True)

    def raise_system_exit(*args, **kwargs): 
        raise SystemExit
    signal.signal(signal.SIGTERM, raise_system_exit)
    signal.signal(signal.SIGHUP, raise_system_exit)
    signal.signal(signal.SIGINT, raise_system_exit)

    database_server = DatabaseServer(args.host, args.port)
    database_server.start()

    """
    import logging
    logging.basicConfig()
    logging.getLogger("database").setLevel(logging.DEBUG)
    """
    
    try:
        print("Press Ctrl+C to end")
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
