from abc import abstractmethod, ABCMeta

#Creating an abstract base class for all future diskFinders to implement
class AbsDiskFinder:

    __metaclass__ = ABCMeta

    @abstractmethod
    def returnDisk(self):
        pass

    @abstractmethod
    def findDevices(self):
        pass

    @abstractmethod
    def formatList(self, deviceList):
        pass

