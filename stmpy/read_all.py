from struct import unpack
import numpy as np
import scipy.io as sio
import os
import re
from stmpy import matio
from datetime import datetime, timedelta


def load(filePath):
    '''
Loads data into python.  Currently supports formats: 3ds, sxm, dat, nvi, nvl, mat, nsp.
Note: mat files are supported as exports from STMView only.
Please include the file extension in the path, e.g. 'file.3ds'

Usage: data = load(filePath)
    '''
    if filePath.endswith('.3ds'):
        return _correct_bias_offset(Nanonis3ds(filePath), '.3ds')

    elif filePath.endswith('.sxm'):
        return NanonisSXM(filePath)

    elif filePath.endswith('.dat'):
        return _correct_bias_offset(NanonisDat(filePath), '.dat')

    elif filePath[-3:] == 'NVI' or filePath[-3:] == 'nvi':
        return NISTnvi(sio.readsav(filePath))

    elif filePath[-3:] == 'NVL' or filePath[-3:] == 'nvl':
        return NISTnvl(sio.readsav(filePath))

    elif filePath.endswith('.nsp'):
        return LongTermSpectrum(filePath)
        
    elif filePath.endswith('.mat'):
        raw_mat = matio.loadmat(filePath)
        mappy_dict = {}
        for key in raw_mat:
            try:
                mappy_dict[key] = matio.Mappy()
                mappy_dict[key].mat2mappy(raw_mat[key])
                print('Created channel: {:}'.format(key))
            except:
                del mappy_dict[key]
                print('Could not convert: {:}'.format(key))
        if len(mappy_dict) == 1: return mappy_dict[mappy_dict.keys()[0]]
        else: return mappy_dict
    else: raise IOError('ERR - Wrong file type.')

def save(filePath, pyObject):
    '''
Save objects from a python workspace to disk.
Currently implemented for the following python data types: nvl, mat.
Currently saves to the following file types: mat.
Please include the file extension in the path, e.g. 'file.mat'

Usage: save(filePath, data)
    '''
    if filePath.endswith('.mat'):
        if pyObject.__class__ == matio.Mappy:
            pyObject.savemat(filePath)
        elif pyObject.__class__ == NISTnvl:
            mappyObject = matio.Mappy()
            mappyObject.nvl2mappy(pyObject)
            mappyObject.savemat(filePath)
    else: raise IOError('ERR - File format not supported.')



####    ____HIDDEN METHODS____    ####

def _correct_bias_offset(data, fileType):
    try:
        if fileType == '.dat':
            I = data.I
        elif fileType == '.3ds':
            I = [np.mean(data.I[ix]) for ix, __ in enumerate(data.en)]
        else:
            print('ERR: Bias offset for {:} not yet implemented'.format(fileType))
            return data
        for ix, (I_low, I_high) in enumerate(zip(I[:-1], I[1:])):
            if np.sign(I_low) != np.sign(I_high):
                en_low, en_high = data.en[ix], data.en[ix+1]
                biasOffset = en_high - I_high * (en_high-en_low) / (I_high - I_low)
                data.en -= biasOffset
                break
        print('Corrected for a bias offset of {:2.2f} meV'.format(biasOffset*1000))
        return data
    except:
        print('ERR: File not in standard format for processing. Could not correct for Bias offset')
        return data



####    ____CLASS DEFINITIONS____   ####

class Nanonis3ds(object):
    def __init__(self,filePath):
        if self._load3ds(filePath):
            try:
                self.LIY = self.data['LIY 1 omega (A)']
                self.didv = [np.mean(layer) for layer in self.LIY]
            except (KeyError):
                print('Does not have channel called LIY 1 omega (A).  Looking for average channel instead...')
                try:
                    self.LIY = self.data['LIY 1 omega [AVG] (A)']
                    self.didv = [np.mean(layer) for layer in self.LIY]
                    print('Found it!')
                except (KeyError):
                    print('ERR: Average channel not found, resort to manual definitions.  Found channels:\n {:}'.format(self.data.keys()))
            try: self.I   = self.data['Current (A)']
            except (KeyError): self.I = self.data['Current [AVG] (A)']
            self.Z   = self.parameters['Scan:Z (m)']
        else: raise NameError('File not found.')

    def _load3ds(self,filePath):
        try: fileObj = open(filePath,'rb')
        except: return 0
        self.header={}
        while True:
            line = fileObj.readline().strip().decode('utf-8')
            if line == ':HEADER_END:': break
            splitLine = line.split('=')
            self.header[splitLine[0]] = splitLine[1]

        self.info={	'params'	:	int(self.header['# Parameters (4 byte)']),
                    'paramName'	:	self.header['Fixed parameters'][1:-1].split(';') +
                                    self.header['Experiment parameters'][1:-1].split(';'),
                    'channels'	:	self.header['Channels'][1:-1].split(';'),
                    'points'	:	int(self.header['Points']),
                    'sizex'		:	int(self.header['Grid dim'][1:-1].split(' x ')[0]),
                    'sizey'		:	int(self.header['Grid dim'][1:-1].split(' x ')[1]),
                    'dataStart'	:	fileObj.tell()
                    }

        self.data = {}; self.parameters = {}
        for channel in self.info['channels']:
            self.data[channel] = np.zeros([self.info['points'],self.info['sizex'],self.info['sizey']])
        for name in self.info['paramName']:
            self.parameters[name] = np.zeros([self.info['sizex'],self.info['sizey']])

#<<<<<<< Updated upstream
        try:
            for ix in range(self.info['sizex']):
                for iy in range(self.info['sizey']):
                    for name in self.info['paramName']:
                        value = unpack('>f',fileObj.read(4))[0]
                        self.parameters[name][ix,iy] = value

                    for channel in self.info['channels']:
                        for ie in range(self.info['points']):
                            value = unpack('>f',fileObj.read(4))[0]
                            self.data[channel][ie,ix,iy] =value
        except:
            print('WARNING - Data set is not complete.')

#=======
        for ix in range(self.info['sizex']):
            for iy in range(self.info['sizey']):
                for name in self.info['paramName']:
                    try:
                        value = unpack('>f',fileObj.read(4))[0]
                        self.parameters[name][ix,iy] = value
                    except:
                        pass

                for channel in self.info['channels']:
                    for ie in range(self.info['points']):
                        try:
                            value = unpack('>f',fileObj.read(4))[0]
                            self.data[channel][ie,ix,iy] =value
                        except:
                            pass
#>>>>>>> Stashed changes
        self.en = np.linspace(self.parameters['Sweep Start'].flatten()[0],
                              self.parameters['Sweep End'].flatten()[0],
                              self.info['points'])

        dataRead = fileObj.tell()
        fileObj.read()
        allData = fileObj.tell()
        if dataRead == allData: print('File import successful.')
        else: print('ERR: Did not reach end of file.')
        fileObj.close()
        return 1

class LongTermSpectrum(object):
    '''
header: a dict containging all parameters
time: time length of the spectrum, in unit of (s)
freq: freq range of the spectrum, in unit of (Hz)
fftI, fftV, or fftSignal:
    current signal >> fftI
    voltage signal >> fftV
    other signal   >> fftSignal 
Example Usage:
import stmpy \nimport matplotlib.pyplot as plt \nimport matplotlib.dates as md \nimport numpy as np \nfrom datetime import datetime \n 
data = stmpy.load('***.nsp')
x=np.array(data.start,dtype='datetime64[s]') \nstepsize = int(np.floor(((data.end - data.start).total_seconds())/data.header['DATASIZEROWS']))
dates = x + np.arange(0,stepsize*data.header['DATASIZEROWS'],stepsize) \nnew_dates=[np.datetime64(ts).astype(datetime) for ts in dates]
datenums=md.date2num(new_dates) \nplt.subplots_adjust(bottom=0.2) \nplt.xticks( rotation=45 ) \nplt.ax=plt.gca() \nxfmt = md.DateFormatter('%Y-%m-%d %H:%M:%S')
plt.ax.xaxis.set_major_formatter(xfmt) \nplt.pcolormesh(datenums, data.freq, data.fftI)#depending on which kind of data used
plt.clim(0,1e-12)#can be different \nplt.ylabel('Frequency (Hz)') \nplt.savefig('pic name.png',dpi = 600,bbox_inches = 'tight') \nplt.show()
    '''
    def __init__(self, filePath):
        self._loadnsp(filePath)
        if self.header['SIGNAL'] == 'Current (A)':
            self.fftI = self.data.T
        elif self.header['SIGNAL'] == 'InternalGeophone (V)':
            self.fftV = self.data.T
        else:
            self.fftSignal = self.data.T

    def _loadnsp(self, filePath):
        try: fileObj = open(filePath, 'rb')
        except: return 0
        self.header = {}
        while True:
            line = fileObj.readline().strip().decode('utf-8')
            if line == ':HEADER_END:': 
                break
            elif re.match('^:.*:$', line):
                tagname = line[1:-1]
            else:
                try:
                    self.header[tagname] = int(line.split('\t')[0])
                except:
                    self.header[tagname] = line.split('\t')[0]

        self.freq = np.linspace(0, np.round(float(self.header['DATASIZECOLS'])*float(self.header['DELTA_f'])),float(self.header['DATASIZECOLS']))
        
        self.start = datetime.strptime(self.header['START_DATE']+self.header['START_TIME'],'%d.%m.%Y%H:%M:%S')
        self.end = datetime.strptime(self.header['END_DATE']+self.header['END_TIME'],'%d.%m.%Y%H:%M:%S')
        self.time = np.linspace(0, (self.end - self.start).total_seconds(), int(self.header['DATASIZEROWS']))

        self.data = np.zeros([int(self.header['DATASIZEROWS']),int(self.header['DATASIZECOLS'])])
        fileObj.read(2) #first two bytes are not data
        try:
            for ix in range(int(self.header['DATASIZEROWS'])):
                for iy in range(int(self.header['DATASIZECOLS'])):
                    value = unpack('>f',fileObj.read(4))[0]
                    self.data[ix,iy] = value
        except:
            print('Error: Data set is not complete')


class NanonisSXM(object):
    def __init__(self, filename):
        self.header = {}
        self.header['filename'] = filename
        self._open()
    
    def _open(self):
        self._file = open(os.path.normpath(self.header['filename']), 'rb')
        s1 = self._file.readline().decode('utf-8')
        if not re.match(':NANONIS_VERSION:', s1):
            print('The file %s does not have the Nanonis SXM'.format(self.header['filename']))
            return
        self.header['version'] = int(self._file.readline())
        while True:
            line = self._file.readline().strip().decode('utf-8')
            if re.match('^:.*:$', line):
                tagname = line[1:-1]
            else:
                if 'Z-CONTROLLER' == tagname:
                    keys = line.split('\t')
                    values = self._file.readline().strip().decode('utf-8').split('\t')
                    self.header['z-controller'] = dict(zip(keys, values))
                elif tagname in ('BIAS', 'REC_TEMP', 'ACQ_TIME', 'SCAN_ANGLE'):
                    self.header[tagname.lower()] = float(line)
                elif tagname in ('SCAN_PIXELS', 'SCAN_TIME', 'SCAN_RANGE', 'SCAN_OFFSET'):
                    self.header[tagname.lower()] = [ float(i) for i in re.split('\s+', line) ]
                elif 'DATA_INFO' == tagname:
                    if 1 == self.header['version']:
                        keys = re.split('\s\s+',line)
                    else:
                        keys = line.split('\t')
                    self.header['data_info'] = []
                    while True:
                        line = self._file.readline().strip().decode('utf-8')
                        if not line:
                            break
                        values = line.strip().split('\t')
                        self.header['data_info'].append(dict(zip(keys, values)))
                elif tagname in ('SCANIT_TYPE','REC_DATE', 'REC_TIME', 'SCAN_FILE', 'SCAN_DIR'):
                    self.header[tagname.lower()] = line
                elif 'SCANIT_END' == tagname:
                    break
                else:
                    if tagname.lower() not in self.header:
                        self.header[tagname.lower()] = line
                    else:
                        self.header[tagname.lower()] += '\n' + line
        if 1 == self.header['version']:
            self.header['scan_pixels'].reverse()
        self._file.readline()
        self._file.read(2) # Need to read the byte \x1A\x04, before reading data
        size = int( self.header['scan_pixels'][0] * self.header['scan_pixels'][1] * 4)
        shape = [int(val) for val in self.header['scan_pixels']]
        self.channels = {}
        for channel in self.header['data_info']:
            if channel['Direction'] == 'both':
                self.channels[channel['Name'] + '_Fwd'] = np.ndarray(shape=shape, dtype='>f', buffer=self._file.read(size))
                self.channels[channel['Name'] + '_Bkd'] = np.ndarray(shape=shape, dtype='>f', buffer=self._file.read(size))
            else:
                self.channels[channel['Name'] + channel['Direction']] = np.ndarray(shape=shape, dtype='>f', buffer=self._file.read(size))
        try:
            self.Z = self.channels['Z_Fwd']
            self.I = self.channels['Current_Fwd']
            self.LIY = self.channels['LIY_1_omega_Fwd']
        except KeyError: print('WARNING:  Could not create standard attributes, look in channels instead.')
        self._file.close()



class NanonisDat(object):
    def __init__(self,filename):
        self.channels = {}
        self.header = {}
        self.header['filename'] = filename
        self._open()
    def _open(self):
        self._file = open(self.header['filename'],'r')
        for line in self._file:
            splitLine = line.split('\t')
            if line[0:6] == '[DATA]':
                channels = self._file.readline().rstrip().split('\t')
                break
            elif line[0:2] != '\n': self.header[splitLine[0]] = splitLine[1]
        allData=[]
        for line in self._file:
            line = line.rstrip().split('\t')
            allData.append(np.array(line, dtype = float))
        allData = np.array(allData)
        try:
            for ix,channel in enumerate(channels):
                self.channels[channel] = allData[:,ix]
        except:
            pass
        self._file.close()
        try:
            self.didv = self.channels['LIY 1 omega (A)']
            self.I = self.channels['Current (A)']
            self.en = self.channels['Bias (V)']
        except (KeyError):
            try:
                self.en = self.channels['Bias calc (V)']
            except (KeyError):
                print('WARNING:  Could not create standard attributes, look in channels instead.')

class NISTnvi(object):
    def __init__(self,nviData):
        self._raw = nviData['imagetosave']
        self.map = self._raw.currentdata[0]
        self.header = {name:self._raw.header[0][name][0] for name in self._raw.header[0].dtype.names}
        self.info = {'FILENAME'    : self._raw.filename[0],
                     'FILSIZE'     : int(self._raw.header[0].filesize[0]),
                     'CHANNELS'    : self._raw.header[0].scan_channels[0],
                     'XSIZE'       : self._raw.xsize[0],
                     'YSIZE'       : self._raw.ysize[0],
                     'TEMPERATURE' : self._raw.header[0].temperature[0],
                     'LOCKIN_AMPLITUDE' : self._raw.header[0].lockin_amplitude[0],
                     'LOCKIN_FREQUENCY' : self._raw.header[0].lockin_frequency[0],
                     'DATE'        : self._raw.header[0].date[0],
                     'TIME'        : self._raw.header[0].time[0],
                     'BIAS_SETPOINT'    : self._raw.header[0].bias_setpoint[0],
                     'BIAS_OFFSET' : self._raw.header[0].bias_offset[0],
                     'BFIELD'      : self._raw.header[0].bfield[0],
                     'ZUNITS'      : self._raw.zunits[0],
					}
        
class NISTnvl(object):
    def __init__(self,nvlData):
        self._raw = nvlData['savestructure']
        self.en = self._raw.energies[0]
        self.map = self._raw.fwddata[0]
        self.ave = [np.mean(layer) for layer in self.map]
        self.header = {name:self._raw.header[0][name][0] for name in self._raw.header[0].dtype.names}
        for name in self._raw.dtype.names:
            if name not in self.header.keys():
                self.header[name] = self._raw[name][0]
        self.info = {}
        try:
            self.info['FILENAME']   = self._raw.filename[0]
        except:
            1
        try:
            self.info['FILSIZE']    = int(self._raw.header[0].filesize[0])
        except:
            1
        try:
            self.info['CHANNELS']   = self._raw.header[0].scan_channels[0]
        except:
            1
        try:
            self.info['XSIZE']      = self._raw.xsize[0]
        except:
            1
        try:
            self.info['YSIZE']      = self._raw.ysize[0]
        except:
            1
        try:
            self.info['TEMPERATURE']= self._raw.header[0].temperature[0]
        except:
            1
        try:
            self.info['LOCKIN_AMPLITUDE']= self._raw.header[0].lockin_amplitude[0]
        except:
            1
        try:
            self.info['LOCKIN_FREQUENCY']= self._raw.header[0].lockin_frequency[0]
        except:
            1
        try:
            self.info['DATE']       = self._raw.header[0].date[0]
        except:
            1
        try:
            self.info['TIME']       = self._raw.header[0].time[0]
        except:
            1
        try:
            self.info['BIAS_SETPOINT'] = self._raw.header[0].bias_setpoint[0]
        except:
            1
        try:
            self.info['BIAS_OFFSET']= self._raw.header[0].bias_offset[0]
        except:
            1
        try:
            self.info['BFIELD']     = self._raw.header[0].bfield[0]
        except:
            1
        try:
            self.info['WINDOWTITLE'] = self._raw.windowtitle[0]
        except:
            1
        try:
            self.info['XYUNITS']    = self._raw.xyunits[0]
        except:
            1
        try:
            self.info['EUNITS']     = self._raw.eunits[0]
        except:
            1




