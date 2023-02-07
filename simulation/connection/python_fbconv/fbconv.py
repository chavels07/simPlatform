# !usr/bin/env python
# -*- coding:utf-8 _*-

import platform
import os
import sys
import json
import shutil
import zipfile
import ctypes
from threading import Lock

class FBConverter:
    _mutex = Lock()
    _mecdata_ver = "2.3.0"
    _platform_windows = "Windows"
    _platform_linux = "Linux"
    _platform_macos = "MacOS"
    _platform_android = "Android"
    _platform_ios = "iOS"
    _machine_aarch64 = "aarch64"
    _machine_x86_64 = "x86_64"
    _machine_AMD64 = "AMD64"
    _dylib_linux = "libfbconv.so"
    _dylib_windows = "fbconv.dll"
    def __init__(self, buf_size = 4096):
        self.platform_system = platform.system()
        self.platform_machine = platform.machine()
        self.buf_size = buf_size
        current_folder = os.path.dirname(__file__)
        if self.platform_system == "Linux":
            if self.platform_machine == "aarch64": 
                self.dylib_path = os.path.join(current_folder, FBConverter._platform_linux + "_" + FBConverter._machine_aarch64, FBConverter._dylib_linux)
            elif self.platform_machine == "x86_64":
                self.dylib_path = os.path.join(current_folder, FBConverter._platform_linux + "_" + FBConverter._machine_x86_64, FBConverter._dylib_linux)
            else:
                sys.exit("FBConverter is not support %s %s Platform." % (self.platform_system, self.platform_machine))
        elif self.platform_system == "Windows":
            if self.platform_machine == "AMD64":
                self.dylib_path = os.path.join(current_folder, FBConverter._platform_windows + "_" + FBConverter._machine_AMD64, FBConverter._dylib_windows)
            else:
                sys.exit("FBConverter is not support %s %s Platform." % (self.platform_system, self.platform_machine))
        else:
            sys.exit("FBConverter is not support %s %s Platform." % (self.platform_system, self.platform_machine))
         
        self.dylib_mod = ctypes.cdll.LoadLibrary(self.dylib_path)
        #void setSchemaFileDir(const uint8_t* _p_in, size_t _n_in);
        self._setSchemaFileDir = self.dylib_mod.setSchemaFileDir
        self._setSchemaFileDir.argtypes = (ctypes.c_char_p, ctypes.c_size_t)
        #
        #int32_t fb2json(uint16_t _data_type, 
        #                const uint8_t* _p_in, 
        #                size_t _n_in,
        #                size_t _max_n, 
        #                uint8_t* _p_out, 
        #                size_t* _n_out);
        self._fb2json = self.dylib_mod.fb2json
        self._fb2json.argtypes = (ctypes.c_ushort, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_char_p, ctypes.POINTER(ctypes.c_size_t))
        self._fb2json.restype = ctypes.c_int
        #int32_t sm_json2fb(uint16_t _data_type,
        #                   const uint8_t* _p_in,       JSON C string
        #                   size_t _n_in,               JSON C string length
        #                   size_t _max_n,              Output buffer max size
        #                   uint8_t* _p_out,            Output buffer
        #                   size_t* _n_out);            Output size
        self._json2fb = self.dylib_mod.json2fb
        self._json2fb.argtypes = (ctypes.c_ushort, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_char_p, ctypes.POINTER(ctypes.c_size_t))
        self._json2fb.restype = ctypes.c_int
        
        current_folder = os.path.dirname(__file__)
        user_dir = os.path.expanduser('~')
        uncompress_dir = os.path.join(user_dir, ".zbmec")
        fbs_dir = os.path.join(uncompress_dir, "fbs")
        fbs_meta_file = os.path.join(uncompress_dir, "fbs", "fbs_meta.dat")
        verification_file = os.path.join(uncompress_dir, "fbs", "verification_ok")
        fbs_default_zip = os.path.join(current_folder, "fbs.zip")
        FBConverter._mutex.acquire()
        if not os.path.exists(verification_file):
            # print("path not exist")
            if os.path.exists(uncompress_dir) == False:
                os.makedirs(uncompress_dir)
            if os.path.exists(fbs_dir):
                shutil.rmtree(fbs_dir)  
            r = zipfile.is_zipfile(fbs_default_zip)
            if r:     
                fz = zipfile.ZipFile(fbs_default_zip, 'r')
                for file in fz.namelist():
                    fz.extract(file, uncompress_dir)       
            else:
                sys.exit('unzip fbs.zip error!')
            
            file = open(verification_file,'w')
            file.write("uncompress finish.")
            file.close()
        else:
            ## check fbs version, update fbs etc.
            self.props = {}
            for line in open(fbs_meta_file): 
                if line == '\n':
                    break
                else:
                    strs = line.split('=', 1)
                    self.props[strs[0].strip()] = strs[-1].strip()
                    
            print(json.dumps(self.props))
            if self.props['version'] != FBConverter._mecdata_ver:
                print("local mecdata updating")
                if os.path.exists(fbs_dir):
                    shutil.rmtree(fbs_dir)  
                r = zipfile.is_zipfile(fbs_default_zip)
                if r:     
                    fz = zipfile.ZipFile(fbs_default_zip, 'r')
                    for file in fz.namelist():
                        fz.extract(file, uncompress_dir)       
                else:
                    sys.exit('unzip fbs.zip error!')
                
                file = open(verification_file,'w')
                file.write("uncompress finish.")
                file.close()
                print("local mecdata updated")
        FBConverter._mutex.release()
        self.set_schemafile_dir(fbs_dir.encode())
    
    def set_schemafile_dir(self, schmeafile_dir):
        arg0_ptr = ctypes.create_string_buffer(schmeafile_dir, self.buf_size)
        arg1     = ctypes.c_size_t(len(schmeafile_dir))
        self._setSchemaFileDir(arg0_ptr,
                               arg1)
    def json2fb(self, model_type, json_string):
        ret_val  = ctypes.c_int(0)
        arg0     = ctypes.c_ushort(model_type)
        arg1_ptr = ctypes.create_string_buffer(json_string, self.buf_size)
        arg2     = ctypes.c_size_t(len(json_string))
        arg3     = ctypes.c_size_t(self.buf_size)
        arg4_ptr = ctypes.create_string_buffer(self.buf_size)
        arg5     = ctypes.c_size_t(0)
        ret_val = self._json2fb(arg0,
                                arg1_ptr, 
                                arg2, 
                                arg3, 
                                arg4_ptr, 
                                ctypes.byref(arg5))
        ret_buf = arg4_ptr.raw[0:arg5.value]
        return ret_val, ret_buf
    def fb2json(self, model_type, fb_in):
        ret_val  = ctypes.c_int(0)
        arg0     = ctypes.c_ushort(model_type)
        arg1_ptr = ctypes.create_string_buffer(fb_in, self.buf_size)
        arg2     = ctypes.c_size_t(len(fb_in))
        arg3     = ctypes.c_size_t(self.buf_size)
        arg4_ptr = ctypes.create_string_buffer(self.buf_size)
        arg5     = ctypes.c_size_t(0)
        ret_val = self._fb2json(arg0,
                               arg1_ptr,
                               arg2,
                               arg3,
                               arg4_ptr,
                               ctypes.byref(arg5))
        ret_json_val = arg4_ptr.raw.decode()
        return ret_val, ret_json_val
     
# fb_convert = FBConverter()
# test_json_str = b'{"scheme_id": 3,"node_id": {"region": 3,"id": 33},"time_span": {"month_filter": ["JAN","FEB"],"day_filter": [5,6,7,8,9,10],"weekday_filter": ["MON","TUE","WED"],"from_time_point": {"hh": 0,"mm": 0,"ss": 0},"to_time_point": {"hh": 8,"mm": 0,"ss": 0}},"cycle": 160,"max_cycle": 1234,"base_signal_scheme_id": 3,"phases": [{"scat_no": "0","movements": ["mv1","mv2"],"green": 30,"yellow": 3,"allred": 4,"min_green": 26,"max_green": 99},{"id": 1,"order": 1,"scat_no": "1","movements": ["mv1","mv2"],"green": 30,"yellow": 3,"allred": 4,"min_green": 26,"max_green": 99},{"id": 2,"order": 2,"scat_no": "2","movements": ["mv1","mv2"],"green": 30,"yellow": 3,"allred": 4,"min_green": 26,"max_green": 99},{"id": 3,"order": 3,"scat_no": "3","movements": ["mv1","mv2"],"green": 30,"yellow": 3,"allred": 4,"min_green": 26,"max_green": 99}]}'

# # #fb_convert.set_schemafile_dir(b'/root/.zbmec/fbs')
# ret_val, ret_buf = fb_convert.json2fb(36, test_json_str)
# print(ret_val)
# print(ret_buf)
# ret_val, ret_json_val = fb_convert.fb2json(36, ret_buf)
# print("b==========")
# print(ret_val)
# print(ret_json_val)
