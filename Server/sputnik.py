# coding=utf-8
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import urlparse
import os
import traceback
import datetime
import math
from stat import *
import json
import urllib2
import gzip
import StringIO
import struct


# encode binary string to ascii string
def binary_encode(v):
    assert isinstance(v, str)
    res = ""
    for i in xrange(0, len(v), 1):
        _h = math.floor(ord(v[i]) / 16)
        _l = ord(v[i]) - (_h * 16)
        res += chr(int(_h + 65))
        res += chr(int(_l + 97))
    return res


# decode ascii string to binary string
def binary_decode(v):
    assert isinstance(v, str)
    arr = ""
    for i in xrange(0, len(v), 2):
        bt = (ord(v[i]) - 65) * 16 + (ord(v[i+1]) - 97)
        arr += chr(bt)
    return arr


class RobloxMeshVertex:
    def __init__(self, px, py, pz, nx, ny, nz, u, v, w, r, g, b, a):
        self.p_x = px
        self.p_y = py
        self.p_z = pz
        self.n_x = nx
        self.n_y = ny
        self.n_z = nz
        self.u = u
        self.v = v
        self.w = w
        self.r = r
        self.g = g
        self.b = b
        self.a = a


class RobloxMeshTriangle:
    def __init__(self, i0, i1, i2):
        self.i0 = i0
        self.i1 = i1
        self.i2 = i2


class RobloxMesh:
    def __init__(self):
        self.vertices = []
        self.triangles = []
        self.min_x = 99999999.0
        self.min_y = 99999999.0
        self.min_z = 99999999.0
        self.max_x = -99999999.0
        self.max_y = -99999999.0
        self.max_z = -99999999.0

    def append_vertex(self, vrx):
        self.min_x = min(self.min_x, vrx.p_x)
        self.min_y = min(self.min_y, vrx.p_y)
        self.min_z = min(self.min_z, vrx.p_z)
        self.max_x = max(self.max_x, vrx.p_x)
        self.max_y = max(self.max_y, vrx.p_y)
        self.max_z = max(self.max_z, vrx.p_z)
        self.vertices.append(vrx)

    def append_triangle(self, idx):
        self.triangles.append(idx)


#
# https://wiki.roblox.com/index.php%3Ftitle%3DRoblox_Mesh_Format
#
# version 1.00
#
# This is the original version of Roblox's mesh format, which is stored purely in ASCII and can be read by humans.
# These files are stored as 3 lines of text:
#
# version 1.00
# num_faces
# data
#
# The num_faces line represents the number of polygons to expect in the data line.
# The data line represents a series of concatenated Vector3 pairs, stored inbetween brackets with the XYZ coordinates
# separated with commas as so: [1.00,1.00,1.00]
#
# You should expect to see num_faces * 9 concatenated Vector3 pairs in this line.
# Every single vertex is represented in the following manner:
# [vX,vY,vZ][nX,nY,nZ][tU,tV,tW]
#
# The 1st pair, [vX,vY,vZ] is the location of the vertex point. In version 1.00, the XYZ values are doubled,
#    so you should scale the values down by 0.5 when converting them to floats. This issue is fixed in version 1.01.
# The 2nd pair, [nX,nY,nZ] is the normal unit vector of the vertex point, which is used to determine how light
#    bounces off of this vertex.
# The 3rd pair, [tU,tV,tW] is the 2D UV texture coordinate of the vertex point, which is used to determine how the
#    mesh's texture is applied to the mesh. The tW coordinate is unused, so you can expect it's value to be zero.
#    One important quirk to note is that the tV coordinate is inverted, so when converting it to a float and
#    storing it, the value should be stored as 1.f - tV.
#
# Every 3 sets of 3 Vector3 pairs are used to form a polygon, hence why you should expect to see num_faces * 9.
#
#
# version 2.00
# The version 2.00 format is a lot more complicated, as it's stored in a binary format and files may differ in
# structure depending on factors that aren't based on the version number. You will need some some advanced knowledge in
# Computer Science to understand this portion of the article. This will be presented in a C syntax.
#
# MeshHeader
# After reading past the version 2.00\n text, the first chunk of data can be represented with the following struct:
#
# struct MeshHeader
# {
# unsigned short sizeofMeshHeader; // Used to verify your MeshHeader struct is the same as this file's MeshHeader struct
# unsigned char sizeofMeshVertex; // Used to verify your MeshVertex struct is the same as this file's MeshVertex struct
# unsigned char sizeofMeshFace; // Used to verify your MeshFace struct is the same as this file 's MeshFace struct
# unsigned int num_vertices; // The number of vertices in this mesh
# unsigned int num_faces; // The number of faces in this mesh
# }
#
# One critical quirk to note, is that sizeofMeshVertex can vary between 36 and 40 bytes, due to the introduction of
# vertex color data to newer meshes. If you don't account for this difference, the mesh may not be read correctly.
#
# MeshVertex
#
# Once you have read the MeshHeader, you should expect to read an array, MeshVertex[num_vertices] vertices;
# using the following struct:
#
# struct MeshVertex
# {
#   float vx, vy, vz; // XYZ coordinate of the vertex
#   float nx, ny, nz; // XYZ coordinate of the vertex's normal
#   float tu, tv, tw; // UV coordinate of the vertex(tw is reserved)
#
#   // WARNING: The following bytes only exist if 'MeshHeader.sizeofMeshVertex' is equal to 40, rather than 36.
#   unsigned char r, g, b, a; // The RGBA color of the vertex
# }
#
# This array represents all of the vertices in the mesh, which can be linked together into faces.
#
# MeshFace
#
# Finally, you should expect to read an array, MeshFace[num_faces] faces; using the following struct:
# struct MeshFace
# {
# 	unsigned int a; // 1st Vertex Index
# 	unsigned int b; // 2nd Vertex Index
# 	unsigned int c; // 3rd Vertex Index
# }
#
# This array represents indexes in the MeshVertex array that was noted earlier.
# The 3 MeshVertex structs that are indexed using the MeshFace are used to form a polygon in the mesh.
#
def parse_roblox_mesh(mesh_data):
    data_stream = StringIO.StringIO(mesh_data)
    header = data_stream.read(12)

    mesh = RobloxMesh()

    if header == 'version 1.00':
        # skip line
        data_stream.readline()
        num_faces = int(data_stream.readline())
        print("old mesh: " + str(num_faces))
        text_data = data_stream.readline()
        text_data = text_data.replace('][', ';')
        text_data = text_data.replace('[', '')
        text_data = text_data.replace(']', '')
        pairs = text_data.split(";")
        pairs_count = len(pairs)
        print(str(pairs_count))
        if pairs_count != (num_faces * 9):
            print("Invalid number of pairs")
            return None

        for i in range(0, pairs_count, 3):
            values = pairs[i + 0].split(",")
            if len(values) != 3:
                print("Invalid number of values")
                return None
            pos_x = float(values[0]) * 0.5
            pos_y = float(values[1]) * 0.5
            pos_z = float(values[2]) * 0.5

            values = pairs[i + 1].split(",")
            if len(values) != 3:
                print("Invalid number of values")
                return None
            nrm_x = float(values[0])
            nrm_y = float(values[1])
            nrm_z = float(values[2])

            values = pairs[i + 2].split(",")
            if len(values) != 3:
                print("Invalid number of values")
                return None
            t_u = float(values[0])
            t_v = float(values[1])
            t_w = float(values[2])

            vrx = RobloxMeshVertex(pos_x, pos_y, pos_z, nrm_x, nrm_y, nrm_z, t_u, t_v, t_w, 1, 1, 1, 1)
            mesh.append_vertex(vrx)

        for i in range(0, num_faces):
            tri = RobloxMeshTriangle(i*3+0, i*3+1, i*3+2)
            mesh.append_triangle(tri)

        return mesh

    if header != 'version 2.00':
        print("Unsupported mesh header: " + str(header))
        return None

    # skip '\n'
    data_stream.read(1)

    sizeof_mesh_header = struct.unpack('H', data_stream.read(2))[0]
    sizeof_mesh_vertex = struct.unpack('B', data_stream.read(1))[0]
    sizeof_mesh_face = struct.unpack('B', data_stream.read(1))[0]
    num_vertices = struct.unpack('I', data_stream.read(4))[0]
    num_faces = struct.unpack('I', data_stream.read(4))[0]

    # print("sizeof_mesh_header = " + str(sizeof_mesh_header))
    # print("sizeof_mesh_vertex = " + str(sizeof_mesh_vertex))
    # print("sizeof_mesh_face = " + str(sizeof_mesh_face))
    # print("num_vertices = " + str(num_vertices))
    # print("num_faces = " + str(num_faces))

    if sizeof_mesh_header != 12:
        print("Unsupported mesh header size: " + str(sizeof_mesh_header))
        return None

    if sizeof_mesh_vertex != 36 and sizeof_mesh_vertex != 40:
        print("Unsupported vertex size: " + str(sizeof_mesh_vertex))
        return None

    if sizeof_mesh_face != 12:
        print("Unsupported face size: " + str(sizeof_mesh_face))
        return None

    for i in range(0, num_vertices):
        pos_x = struct.unpack('f', data_stream.read(4))[0]
        pos_y = struct.unpack('f', data_stream.read(4))[0]
        pos_z = struct.unpack('f', data_stream.read(4))[0]
        nrm_x = struct.unpack('f', data_stream.read(4))[0]
        nrm_y = struct.unpack('f', data_stream.read(4))[0]
        nrm_z = struct.unpack('f', data_stream.read(4))[0]
        t_u = struct.unpack('f', data_stream.read(4))[0]
        t_v = struct.unpack('f', data_stream.read(4))[0]
        t_w = struct.unpack('f', data_stream.read(4))[0]
        if sizeof_mesh_vertex == 40:
            col_r = struct.unpack('B', data_stream.read(1))[0]
            col_g = struct.unpack('B', data_stream.read(1))[0]
            col_b = struct.unpack('B', data_stream.read(1))[0]
            col_a = struct.unpack('B', data_stream.read(1))[0]
        else:
            col_r = 0xff
            col_g = 0xff
            col_b = 0xff
            col_a = 0xff
        vrx = RobloxMeshVertex(pos_x, pos_y, pos_z, nrm_x, nrm_y, nrm_z, t_u, t_v, t_w, col_r, col_g, col_b, col_a)
        mesh.append_vertex(vrx)

    for i in range(0, num_faces):
        index0 = struct.unpack('I', data_stream.read(4))[0]
        index1 = struct.unpack('I', data_stream.read(4))[0]
        index2 = struct.unpack('I', data_stream.read(4))[0]
        tri = RobloxMeshTriangle(index0, index1, index2)
        mesh.append_triangle(tri)

    return mesh


def save_mesh_to_obj(target_dir, mesh_id, mesh):

    size_x = mesh.max_x - mesh.min_x
    size_y = mesh.max_y - mesh.min_y
    size_z = mesh.max_z - mesh.min_z
    print(size_x)
    print(size_y)
    print(size_z)

    print(mesh_id)
    file_name = target_dir + '/' + str(mesh_id) + '.obj'
    print(file_name)

    file_handle = open(file_name, 'w+')

    for v in mesh.vertices:
        line = 'v ' + str(v.p_x / size_x) + ' ' + str(v.p_y / size_y) + ' ' + str(v.p_z / size_z) + '\n'
        file_handle.write(line)

    for v in mesh.vertices:
        line = 'vt ' + str(v.u) + ' ' + str(v.v) + '\n'
        file_handle.write(line)

    for v in mesh.vertices:
        line = 'vn ' + str(v.n_x) + ' ' + str(v.n_y) + ' ' + str(v.n_z) + '\n'
        file_handle.write(line)

    line = 'g m' + str(mesh_id) + '\n'
    file_handle.write(line)

    for t in mesh.triangles:
        i0 = str(t.i0 + 1)
        i1 = str(t.i1 + 1)
        i2 = str(t.i2 + 1)
        line = 'f ' + i0 + '/' + i0 + '/' + i0 + ' ' + i1 + '/' + i1 + '/' + i1 + ' ' + i2 + '/' + i2 + '/' + i2 + '\n'
        file_handle.write(line)

    file_handle.close()
    return file_name


def save_scene_to_mel(file_name, scene_objects):

    file_handle = open(file_name, 'w+')

    cmd = 'string $loc[];\n'
    file_handle.write(cmd)
    cmd = 'string $geom[];\n'
    file_handle.write(cmd)

    for scene_object in scene_objects:
        full_name = scene_object['full_name']
        full_name = full_name.replace('.', '_')
        full_name = full_name.replace('~', '_')
        full_name = full_name.replace(' ', '_')
        full_name = full_name.replace('(', '_')
        full_name = full_name.replace(')', '_')
        full_name = full_name.replace('/', '_')
        full_name = full_name.replace('\\', '_')
        pos_x = scene_object['pos_x']
        pos_y = scene_object['pos_y']
        pos_z = scene_object['pos_z']
        rot_x = scene_object['rot_x'] * 57.2958
        rot_y = scene_object['rot_y'] * 57.2958
        rot_z = scene_object['rot_z'] * 57.2958
        scl_x = scene_object['scl_x']
        scl_y = scene_object['scl_y']
        scl_z = scene_object['scl_z']
        shape = scene_object['shape']

        cmd = '$loc = `spaceLocator -n ' + full_name + '`;\n'
        file_handle.write(cmd)

        if shape == 'Enum.PartType.Block':
            cmd = '$geom = `polyCube -n block`;\n'
            file_handle.write(cmd)
            cmd = 'parent $geom[0] $loc[0];\n'
            file_handle.write(cmd)

        if shape == 'Enum.PartType.Ball':
            cmd = '$geom = `polySphere -r 0.5 -n ball`;\n'
            file_handle.write(cmd)
            cmd = 'parent $geom[0] $loc[0];\n'
            file_handle.write(cmd)

        if shape == 'Enum.PartType.Cylinder':
            cmd = '$geom = `polyCylinder -r 0.5 -h 1 -n cyl`;\n'
            file_handle.write(cmd)
            cmd = 'setAttr($geom[0] + ".rotateZ") -90;\n'
            file_handle.write(cmd)
            cmd = 'parent $geom[0] $loc[0];\n'
            scl = min(scl_y, scl_z)
            scl_y = scl
            scl_z = scl
            file_handle.write(cmd)

        if (shape == 'MeshPart' or shape == 'SpecialMesh') and 'mesh_file_name' in scene_object:
            mesh_id = scene_object['mesh_id']
            mesh_file_name = scene_object['mesh_file_name']
            cmd = 'file -import -type "OBJ" "' + mesh_file_name + '";\n'
            file_handle.write(cmd)
            if shape == 'SpecialMesh':
                mesh_bbox_x = scene_object['mesh_bbox_x']
                mesh_bbox_y = scene_object['mesh_bbox_y']
                mesh_bbox_z = scene_object['mesh_bbox_z']
                cmd = 'setAttr |m' + str(mesh_id) + '.scaleX ' + str(mesh_bbox_x) + ';\n'
                file_handle.write(cmd)
                cmd = 'setAttr |m' + str(mesh_id) + '.scaleY ' + str(mesh_bbox_y) + ';\n'
                file_handle.write(cmd)
                cmd = 'setAttr |m' + str(mesh_id) + '.scaleZ ' + str(mesh_bbox_z) + ';\n'
                file_handle.write(cmd)
            cmd = 'parent |m' + str(mesh_id) + ' $loc[0];\n'
            file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".translateX") ' + str(pos_x) + ';\n'
        file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".translateY") ' + str(pos_y) + ';\n'
        file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".translateZ") ' + str(pos_z) + ';\n'
        file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".rotateX") ' + str(rot_x) + ';\n'
        file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".rotateY") ' + str(rot_y) + ';\n'
        file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".rotateZ") ' + str(rot_z) + ';\n'
        file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".scaleX") ' + str(scl_x) + ';\n'
        file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".scaleY") ' + str(scl_y) + ';\n'
        file_handle.write(cmd)

        cmd = 'setAttr($loc[0] + ".scaleZ") ' + str(scl_z) + ';\n'
        file_handle.write(cmd)

    file_handle.close()


def export_roblox_scene(file_name, scene_json):
    print(scene_json)
    scene_objects = json.loads(scene_json)
    target_dir = os.path.dirname(file_name)

    processed_meshes = {}
    id_to_mesh = {}

    for scene_object in scene_objects:
        mesh_url = scene_object['mesh_id'].rstrip()
        mesh_url = mesh_url.replace('rbxassetid://', 'http://www.roblox.com/asset/?id=')
        mesh_id = mesh_url.replace('http://www.roblox.com/asset/?id=', '')

        if mesh_id not in processed_meshes:
            if len(mesh_url) > 0:
                print("Fetch: " + mesh_url)
                request = urllib2.Request(mesh_url)
                request.add_header('Accept-Encoding', 'gzip')
                response = urllib2.urlopen(request)
                if response.info().get('Content-Encoding') == 'gzip':
                    mesh_compressed_data = response.read()
                    mesh_compressed_stream = StringIO.StringIO(mesh_compressed_data)
                    gzip_reader = gzip.GzipFile(fileobj=mesh_compressed_stream)
                    mesh_data = gzip_reader.read()
                else:
                    mesh_data = response.read()
                mesh = parse_roblox_mesh(mesh_data)

                if mesh is not None:
                    mesh_file_name = save_mesh_to_obj(target_dir, mesh_id, mesh)
                    scene_object['mesh_file_name'] = mesh_file_name
                    processed_meshes[mesh_id] = mesh_file_name
                    id_to_mesh[mesh_id] = mesh
        else:
            scene_object['mesh_file_name'] = processed_meshes[mesh_id]

        if len(mesh_id) > 0 and mesh_id in id_to_mesh:
            mesh = id_to_mesh[mesh_id]
            scene_object['mesh_bbox_x'] = mesh.max_x - mesh.min_x
            scene_object['mesh_bbox_y'] = mesh.max_y - mesh.min_y
            scene_object['mesh_bbox_z'] = mesh.max_z - mesh.min_z
        else:
            scene_object['mesh_bbox_x'] = 1.0
            scene_object['mesh_bbox_y'] = 1.0
            scene_object['mesh_bbox_z'] = 1.0

        scene_object['mesh_id'] = mesh_id

    save_scene_to_mel(file_name, scene_objects)


# noinspection PyBroadException
class S(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_HEAD(self):
        self._set_headers()

    def do_GET(self):
        if self.client_address[0] != '127.0.0.1':
            print ('Unauthorized access attempt from ' + str(self.client_address))
            self.send_error(404)
            return
        url = urlparse.urlparse(self.path)
        cmd = url.path
        params = urlparse.parse_qs(url.query)
        if cmd == '/ver':
            return self._ver(params)
        if cmd == '/getcwd':
            return self._getcwd()
        if cmd == '/dirlist':
            return self._dirlist(params)
        if cmd == '/read':
            return self._read(params)
        if cmd == '/stat':
            return self._stat(params)
        print('Unknown command: ' + cmd)
        print(self.path)
        self.send_error(404)

    def do_POST(self):
        if self.client_address[0] != '127.0.0.1':
            print ('Unauthorized access attempt from ' + str(self.client_address))
            self.send_error(404)
            return
        url = urlparse.urlparse(self.path)
        cmd = url.path
        params = urlparse.parse_qs(url.query)
        if cmd == '/chdir':
            return self._chdir(params)
        if cmd == '/write':
            return self._write(params)
        if cmd == '/scene_export':
            return self._export_scene(params)
        print('Unknown command: ' + cmd)
        print(self.path)
        self.send_error(404)

    def _ver(self, params):
        try:
            if 'guid' in params:
                guid_encoded = params['guid'][0]
                guid = binary_decode(guid_encoded)
                guid_answer = binary_encode(guid)
                self._set_headers()
                self.wfile.write('{ "result" : "ok", "ver" : "1.0", "guid" : "' + guid_answer + '" }')
            else:
                self._set_headers()
                self.wfile.write('{ "result" : "ok", "ver" : "1.0" }')
        except Exception:
            print ('ver exception')
            print(traceback.format_exc())
            self._set_headers()
            self.wfile.write('{ "result" : "error" }')

    def _getcwd(self):
        try:
            current_dir = os.getcwd()
            current_dir = current_dir.replace('\\', '/')
            current_dir = current_dir.rstrip('/')
            current_dir += '/'
            respond = '{ "result" : "ok", "dir" : "' + current_dir + '" }'
            self._set_headers()
            self.wfile.write(respond)
        except Exception:
            print ('getcwd exception')
            print(traceback.format_exc())
            self._set_headers()
            self.wfile.write('{ "result" : "error" }')

    def _chdir(self, params):
        try:
            dir_name = params['dir'][0]
            dir_name = dir_name.replace('\\', '/')
            dir_name = dir_name.rstrip('/')
            dir_name += '/'
            os.chdir(dir_name)
            self._set_headers()
            self.wfile.write('{ "result" : "ok" }')
        except Exception:
            print ('chdir exception')
            print(traceback.format_exc())
            self._set_headers()
            self.wfile.write('{ "result" : "error" }')

    def _export_scene(self, params):
        try:
            file_name = params['file'][0]
            file_name = file_name.replace('\\', '/')
            print("Scene export : " + file_name)

            data_len = int(self.headers.getheader('content-length', 0))
            data_body = self.rfile.read(data_len)

            export_roblox_scene(file_name, data_body)

            self._set_headers()
            self.wfile.write('{ "result" : "ok" }')
        except Exception:
            print ('write exception')
            print(traceback.format_exc())
            self._set_headers()
            self.wfile.write('{ "result" : "error" }')

    def _write(self, params):
        try:
            data_len = int(self.headers.getheader('content-length', 0))
            data_body = self.rfile.read(data_len)
            data = binary_decode(data_body)
            file_name = params['file'][0]
            file_name = file_name.replace('\\', '/')
            file_handle = open(file_name, "wb")
            file_handle.write(data)
            file_handle.close()
            self._set_headers()
            self.wfile.write('{ "result" : "ok" }')
        except Exception:
            print ('write exception')
            print(traceback.format_exc())
            self._set_headers()
            self.wfile.write('{ "result" : "error" }')

    def _stat(self, params):
        try:
            path_name = params['path'][0]
            path_name = path_name.replace('\\', '/')
            path_stat = os.stat(path_name)
            mode = path_stat.st_mode

            is_dir = False
            if S_ISDIR(mode):
                is_dir = True

            is_file = False
            if S_ISREG(mode):
                is_file = True

            self._set_headers()
            self.wfile.write('{ "result" : "ok", '
                             '"payload": { "is_exist" : true, "is_dir" : ' + str(is_dir).lower() +
                             ', "is_file" : ' + str(is_file).lower() +
                             ', "size" : ' + str(path_stat.st_size) + '} }')

        except os.error:
            self._set_headers()
            self.wfile.write('{ "result" : "ok", "payload": { "is_exist" : false, "is_dir" : false, '
                             '"is_file" : false, "size" : 0 } }')

        except Exception:
            print ('stat exception')
            print(traceback.format_exc())
            self._set_headers()
            self.wfile.write('{ "result" : "error" }')

    def _read(self, params):
        try:
            file_name = params['file'][0]
            file_name = file_name.replace('\\', '/')
            file_handle = open(file_name, "rb")
            file_content = file_handle.read()
            file_handle.close()
            file_size = os.path.getsize(file_name)
            data = binary_encode(file_content)
            respond = '{ "result" : "ok", "content" : "' + data + '", "size" : ' + str(file_size) + ' }'
            self._set_headers()
            self.wfile.write(respond)
        except Exception:
            print ('read exception')
            print(traceback.format_exc())
            self._set_headers()
            self.wfile.write('{ "result" : "error" }')

    def _dirlist(self, params):
        try:
            dir_name = os.getcwd()
            if 'dir' in params:
                dir_name = params['dir'][0]
            dir_name = dir_name.replace('\\', '/')
            dir_name = dir_name.rstrip('/')
            dirs = os.listdir(dir_name)
            dirs.sort()

            json_files = ''
            json_dirs = ''

            for short_name in dirs:
                short_name = short_name.replace('\\', '/')
                short_name = short_name.rstrip('/')
                long_name = dir_name + '/' + short_name
                if os.path.isdir(long_name):
                    long_name += '/'
                    short_name += '/'
                    if len(json_dirs):
                        json_dirs += ', '
                    json_dirs += '{ "short_name" : "' + short_name + '", '
                    json_dirs += '"long_name" : "' + long_name + '" }'
                elif os.path.isfile(long_name):
                    file_size = os.path.getsize(long_name)
                    time_stamp = os.path.getmtime(long_name)
                    if len(json_files):
                        json_files += ', '
                    json_files += '{ "short_name" : "' + short_name + '", '
                    json_files += '"long_name" : "' + long_name + '", '
                    json_files += '"size" : ' + str(file_size) + ', '
                    json_files += '"unix_time" : "' + str(time_stamp) + '", '
                    json_files += '"str_time" : "'
                    json_files += datetime.datetime.fromtimestamp(time_stamp).strftime('%Y-%m-%d %H:%M:%S')
                    json_files += '" }'
                else:
                    print ('unknown')

            respond = '{ "result" : "ok", "files": [' + json_files + '], "dirs": [' + json_dirs + '] }'
            self._set_headers()
            self.wfile.write(respond)

        except Exception:
            print ('dirlist exception')
            print(traceback.format_exc())
            self._set_headers()
            self.wfile.write('{ "result" : "error" }')


def run(server_class=HTTPServer, handler_class=S, port=8002):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print ('Starting sputnik server...')
    httpd.serve_forever()


run()
