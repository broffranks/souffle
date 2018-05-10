#include "ProfileDatabase.h"

int main() {
    souffle::ProfileDatabase x;
    x.addSizeEntry({"akey"}, 1);
    x.addSizeEntry({"a", "b", "bkey"}, 2);
    x.addSizeEntry({"a", "c", "bkey"}, 3);
    x.addTextEntry({"a", "x", "akey"}, "blabla");
    x.print(std::cout);

    std::cout << "\n\nSum of bkey:" << x.computeSum({"a", "bkey"}) << std::endl;

    return 0;
}
