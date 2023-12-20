from collections import OrderedDict

class FixedSizeDict:
    def __init__(self, max_size=10):
        self.store = OrderedDict()
        self.max_size = max_size
    
    def __setitem__(self, key, value):
        self.store[key] = value
        self.cleanup()
    
    def __getitem__(self, key):
        return self.store[key]

    def __delitem__(self, key):
        del self.store[key]

    def __contains__(self, key):
        return key in self.store
    
    def __len__(self):
        return len(self.store)

    def cleanup(self):
        while len(self.store) > self.max_size:
            self.store.popitem(last=False)

    def __repr__(self):
        return repr(self.store)